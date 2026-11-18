"""Turn cached LLM extractions and summary-table rows into the flood event dataset.

Steps:
1. Events from the LLM cache (flood-like rows): one per extracted incident.
2. Events from the summary table alone for landslide and collapse rows
   (district level, not training positives).
3. Geocode each event: village (gazetteer, within the district) -> tehsil
   (alias table) -> district. A village that conflicts with a stated tehsil is
   dropped. Only gazetteer names are stored as villages, so a person's name
   mis-read as a village cannot reach the output.
4. De-duplicate: same district, same positive/non-positive class, same tehsil,
   dates within 1 day of each other -> one event (earliest date, richest
   record). A district-level positive within 1 day of a tehsil-level positive
   in the same district is folded into it.
5. Write `data/events/flood_events.parquet`, a GeoJSON for the map viewer, a
   spot-check sheet (private), and `reports/m1_events_qa.md` (counts only).

Usage: python -m pipelines.pdma.build_events
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from backend.app.config import get_settings
from backend.app.config.region import CANDIDATE_DISTRICTS
from backend.app.contracts import EventType, FloodEvent, GeocodeLevel, is_positive
from backend.app.geo import AdminNames, TehsilLocator, name_key
from pipelines.pdma.extract import categorise, iter_reports
from pipelines.pdma.redact import has_name_markers

LEVEL_RANK = {GeocodeLevel.VILLAGE: 2, GeocodeLevel.TEHSIL: 1, GeocodeLevel.DISTRICT: 0}
TYPE_RANK = {EventType.CLOUDBURST: 0, EventType.FLASH_FLOOD: 1, EventType.FLOOD: 2,
             EventType.DROWNING: 3, EventType.LANDSLIDE: 4, EventType.ROOF_COLLAPSE: 5,
             EventType.OTHER: 6}
MAX_DATE_LAG_DAYS = 15  # an event date more than this before the report is not trusted
VILLAGE_FUZZY = 87
TEHSIL_FUZZY = 75
# Common parts of place names; a sub-phrase made only of these is not a place.
GENERIC_PLACE_WORDS = {
    "banda", "kalay", "kalle", "kali", "killi", "kili", "kille", "kot", "dheri", "dherai",
    "bala", "payeen", "payan", "khwar", "nullah", "nala", "mouza", "halqa", "bazar",
    "bazaar", "chowk", "sar", "ghundai", "dara", "darra", "kandao", "cham", "abad",
    "village", "mohallah", "mohalla", "colony", "road", "bridge", "khel", "kheil", "upper",
    "lower", "new", "old", "jar", "tangi", "bandai", "maira", "patay", "gari", "garhi",
}


@dataclass
class Draft:
    date: dt.date
    report_date: dt.date
    district: str
    district_slug: str | None
    event_type: EventType
    source_dsrid: int
    confidence: float
    deaths: int | None = None
    houses_damaged: int | None = None
    tehsil: str | None = None
    tehsil_id: str | None = None
    village: str | None = None
    lat: float | None = None
    lon: float | None = None
    level: GeocodeLevel = GeocodeLevel.DISTRICT
    place_role: str | None = None
    water_body: str | None = None
    n_reports: int = 1
    dsrids: set[int] = field(default_factory=set)


# ---- Geocoding ------------------------------------------------------------------

class Geocoder:
    def __init__(self, ref_dir: Path) -> None:
        self.names = AdminNames.from_dir(ref_dir)
        # Within one district there are only 5-9 tehsils, so a looser cutoff is safe
        # ("Besham" -> Bisham, "Chakisser" -> Chakisar, "Khudakhel" -> Khado Khel).
        self.tehsil_names = AdminNames.from_dir(ref_dir, fuzzy_cutoff=TEHSIL_FUZZY)
        self.locator = TehsilLocator.from_geojson(ref_dir / "tehsils.geojson")
        self.region_districts = {r.tehsil_id.split("__")[0] for r in self.locator.regions}
        self.places: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        with (ref_dir / "gazetteer.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                keys = {name_key(row["name"])} | {name_key(a) for a in row["alt_names"].split("|") if a}
                for key in keys - {""}:
                    self.places[row["district_slug"]][key].append(row)

    @staticmethod
    def phrases(text: str) -> list[str]:
        """The full text, then every run of consecutive words, longest first.

        "Bhai Kalay Pirbaba Daggar" -> the whole, "Bhai Kalay Pirbaba", ...,
        "Daggar". Reports often join a village and its tehsil in one string.
        """

        words = text.replace(",", " ").split()
        out: list[str] = []
        for size in range(len(words), 0, -1):
            for start in range(len(words) - size + 1):
                out.append(" ".join(words[start:start + size]))
        return out

    def _lookup(self, district: str, key: str, *, fuzzy: bool = True) -> list[dict]:
        index = self.places.get(district, {})
        if key in index:
            return index[key]
        if fuzzy and len(key) >= 6:  # fuzzy only for longer names, to avoid false matches
            best = process.extractOne(key, index.keys(), scorer=fuzz.ratio, score_cutoff=VILLAGE_FUZZY)
            if best:
                return index[best[0]]
        return []

    def _village(self, district: str, name: str, tehsil_id: str | None) -> dict | None:
        full = name_key(name)
        for phrase in self.phrases(name):
            key = name_key(phrase)
            if len(key) < 4:
                continue
            if key != full and all(w.lower() in GENERIC_PLACE_WORDS for w in phrase.split()):
                continue
            hits = self._lookup(district, key, fuzzy=key == full or len(key) >= 7)
            if not hits:
                continue
            if tehsil_id:
                hits = [h for h in hits if h["tehsil_id"] == tehsil_id]
                if hits:
                    return hits[0]
                continue
            if len({h["tehsil_id"] for h in hits}) == 1:
                return hits[0]
        return None  # not found, or the same name in several tehsils (ambiguous)

    def _tehsil(self, district: str, text: str, *, exact_only: bool = False) -> str | None:
        for phrase in self.phrases(text):
            matches = self.tehsil_names.resolve_tehsil(phrase, district)
            if matches and (not exact_only or matches[0].method == "exact"):
                return matches[0].tehsil_id
        return None

    def geocode(self, draft: Draft, tehsil_text: str | None, villages: list[str]) -> Draft:
        district = draft.district_slug
        if district not in self.region_districts:
            return draft
        tehsil_id = self._tehsil(district, tehsil_text) if tehsil_text else None
        if tehsil_id is None:  # a tehsil name inside a village string is a hint
            for village in villages:
                tehsil_id = self._tehsil(district, village, exact_only=True)
                if tehsil_id:
                    break
        for village in villages:
            hit = self._village(district, village, tehsil_id)
            if hit:
                region = self.locator.get(hit["tehsil_id"])
                return replace(draft, village=hit["name"], lat=float(hit["lat"]), lon=float(hit["lon"]),
                               tehsil_id=hit["tehsil_id"], tehsil=region.tehsil if region else None,
                               level=GeocodeLevel.VILLAGE)
        if tehsil_id:
            region = self.locator.get(tehsil_id)
            return replace(draft, tehsil_id=tehsil_id, tehsil=region.tehsil,
                           lat=region.centroid_lat, lon=region.centroid_lon, level=GeocodeLevel.TEHSIL)
        return draft


# ---- Drafts from sources ------------------------------------------------------------

def _parse_date(text: str | None, report_date: dt.date) -> tuple[dt.date, bool]:
    try:
        value = dt.date.fromisoformat(text) if text else None
    except ValueError:
        value = None
    if value is None or not (report_date - dt.timedelta(days=MAX_DATE_LAG_DAYS) <= value <= report_date + dt.timedelta(days=1)):
        return report_date, False
    return value, True


def drafts_from_llm(cache_dir: Path, geocoder: Geocoder, stats: Counter) -> list[Draft]:
    drafts: list[Draft] = []
    for path in sorted(cache_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        report_date = dt.date.fromisoformat(record["report_date"])
        incidents = record["result"]["incidents"]
        stats["llm_records"] += 1
        if not incidents:
            stats["llm_no_incident"] += 1
        for inc in incidents:
            date, ok = _parse_date(inc["event_date"], report_date)
            stats["date_ok" if ok else "date_fallback"] += 1
            single = len(incidents) == 1
            water = inc.get("water_body")
            if water and has_name_markers(water):
                water = None
            draft = Draft(
                date=date, report_date=report_date, district=record["district_raw"],
                district_slug=record["district_slug"], event_type=EventType(inc["event_type"]),
                source_dsrid=record["dsrid"],
                confidence=float(inc["confidence"]) * (1.0 if ok else 0.8),
                deaths=inc["deaths"] if inc["deaths"] is not None else (record["summary"]["deaths"] if single else None),
                houses_damaged=inc["houses_damaged"] if inc["houses_damaged"] is not None else (
                    record["summary"]["houses_damaged"] if single else None),
                place_role=inc["place_role"], water_body=water, dsrids={record["dsrid"]},
            )
            drafts.append(geocoder.geocode(draft, inc.get("tehsil"), inc.get("villages") or []))
    return drafts


def drafts_from_tables(raw_dir: Path, names: AdminNames, stats: Counter) -> list[Draft]:
    drafts: list[Draft] = []
    for report in iter_reports(raw_dir):
        if report.report_date is None:
            continue
        for row in report.summary:
            group = categorise(row, report.details.get(row.district_raw, []))
            if group not in ("landslide", "collapse"):
                continue
            stats[f"table_{group}"] += 1
            drafts.append(Draft(
                date=report.report_date, report_date=report.report_date, district=row.district_raw,
                district_slug=names.resolve_district(row.district_raw),
                event_type=EventType.LANDSLIDE if group == "landslide" else EventType.ROOF_COLLAPSE,
                source_dsrid=report.dsrid, confidence=0.6, deaths=row.deaths,
                houses_damaged=row.houses_damaged, dsrids={report.dsrid},
            ))
    return drafts


# ---- De-duplication ------------------------------------------------------------------

def _richness(d: Draft) -> tuple:
    return (LEVEL_RANK[d.level], d.place_role == "incident", d.confidence, d.deaths or 0,
            -TYPE_RANK[d.event_type])


def _merge(cluster: list[Draft]) -> Draft:
    best = max(cluster, key=_richness)
    dsrids = set().union(*(d.dsrids for d in cluster))
    return replace(
        best,
        date=min(d.date for d in cluster),
        event_type=min((d.event_type for d in cluster), key=TYPE_RANK.get),
        deaths=max((d.deaths for d in cluster if d.deaths is not None), default=None),
        houses_damaged=max((d.houses_damaged for d in cluster if d.houses_damaged is not None), default=None),
        n_reports=len(dsrids), dsrids=dsrids,
    )


def deduplicate(drafts: list[Draft]) -> list[Draft]:
    groups: dict[tuple, list[Draft]] = defaultdict(list)
    for d in drafts:
        groups[(d.district_slug or d.district.lower(), is_positive(d.event_type), d.tehsil_id)].append(d)
    merged: list[Draft] = []
    for items in groups.values():
        items.sort(key=lambda d: d.date)
        cluster = [items[0]]
        for d in items[1:]:
            if (d.date - cluster[-1].date).days <= 1:
                cluster.append(d)
            else:
                merged.append(_merge(cluster))
                cluster = [d]
        merged.append(_merge(cluster))

    # Fold district-level positives into a tehsil-level positive nearby in time.
    located = defaultdict(list)
    for d in merged:
        if is_positive(d.event_type) and d.tehsil_id:
            located[d.district_slug].append(d.date)
    out = []
    for d in merged:
        if is_positive(d.event_type) and d.tehsil_id is None and any(
            abs((d.date - other).days) <= 1 for other in located.get(d.district_slug, [])
        ):
            continue
        out.append(d)
    return sorted(out, key=lambda d: (d.date, d.district, d.tehsil_id or ""))


# ---- Output ----------------------------------------------------------------------------

def to_events(drafts: list[Draft]) -> list[FloodEvent]:
    events = []
    for d in drafts:
        key = f"{d.district_slug or d.district}|{d.tehsil_id}|{d.date}|{is_positive(d.event_type)}"
        events.append(FloodEvent(
            event_id="evt_" + hashlib.sha1(key.encode()).hexdigest()[:10],
            date=d.date, report_date=d.report_date, district=d.district,
            tehsil=d.tehsil, tehsil_id=d.tehsil_id, village=d.village,
            lat=round(d.lat, 5) if d.lat is not None else None,
            lon=round(d.lon, 5) if d.lon is not None else None,
            geocode_level=d.level, event_type=d.event_type,
            deaths=d.deaths, houses_damaged=d.houses_damaged,
            source_dsrid=d.source_dsrid, extract_confidence=round(min(d.confidence, 1.0), 3),
            place_role=d.place_role, water_body=d.water_body, n_reports=d.n_reports,
        ))
    return events


# ---- Manual corrections (from the human spot check) -----------------------------------

CORRECTABLE = {"date", "district", "tehsil", "tehsil_id", "village", "lat", "lon",
               "geocode_level", "event_type", "place_role"}


def apply_corrections(events: list[FloodEvent], path: Path, stats: Counter) -> list[FloodEvent]:
    """Apply `event_id,field,value,reason` rows. An empty value clears the field.

    The event_id is the one printed in spot_check.csv, so a correction keeps working
    when the dataset is rebuilt. Unknown ids are reported, not silently ignored.
    """

    if not path.is_file():
        return events
    by_id: dict[str, dict] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            field = row["field"].strip()
            if field not in CORRECTABLE:
                raise ValueError(f"Field {field!r} cannot be corrected")
            value = row["value"].strip()
            by_id.setdefault(row["event_id"].strip(), {})[field] = value or None
    out = []
    for e in events:
        changes = by_id.pop(e.event_id, None)
        if changes:
            data = e.model_dump()
            data.update(changes)
            e = FloodEvent.model_validate(data)
            stats["corrected_events"] += 1
        out.append(e)
    for missing in by_id:
        print(f"warning: correction for unknown event {missing}")
    return out


def write_outputs(events: list[FloodEvent], out_dir: Path) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([{**e.model_dump(mode="python"), "is_positive": e.is_positive} for e in events])
    frame["event_type"] = frame["event_type"].map(lambda v: getattr(v, "value", v))
    frame["geocode_level"] = frame["geocode_level"].map(lambda v: getattr(v, "value", v))
    frame.to_parquet(out_dir / "flood_events.parquet", index=False)

    features = []
    for e in events:
        if e.lat is None:
            continue
        props = e.model_dump(mode="json")
        props["is_positive"] = e.is_positive
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [e.lon, e.lat]},
                         "properties": props})
    (out_dir / "flood_events.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8")
    return frame


def write_spot_check(events: list[FloodEvent], path: Path, n: int = 50, seed: int = 7) -> None:
    positives = [e for e in events if e.is_positive]
    sample = random.Random(seed).sample(positives, min(n, len(positives)))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["event_id", "date", "district", "tehsil", "village", "event_type", "deaths",
                         "source_dsrid", "report_url", "date_correct (y/n)", "district_correct (y/n)",
                         "tehsil_correct (y/n/na)", "notes"])
        for e in sorted(sample, key=lambda e: e.date):
            writer.writerow([e.event_id, e.date, e.district, e.tehsil or "", e.village or "",
                             e.event_type.value, e.deaths if e.deaths is not None else "", e.source_dsrid,
                             f"https://rms.pdma.gov.pk/ViewDSR.aspx?DSRID={e.source_dsrid}", "", "", "", ""])


MANUAL_MARKER = "<!-- manual sections below: kept on rebuild -->"


def write_qa(frame: pd.DataFrame, stats: Counter, path: Path, n_reports: int, last_report: str) -> dict:
    pos = frame[frame["is_positive"]]
    candidate = {d.name for d in CANDIDATE_DISTRICTS}
    pos_c = pos[pos["district"].isin(candidate)]
    tehsil_or_better = pos_c[pos_c["geocode_level"].isin(["village", "tehsil"])]
    district_days = pos.groupby(["district", "date"]).ngroups
    district_days_c = pos_c.groupby(["district", "date"]).ngroups
    share = len(tehsil_or_better) / len(pos_c) if len(pos_c) else 0.0
    gate = {
        "positive_district_days_candidates": district_days_c,
        "share_tehsil_or_better_candidates": round(share, 3),
        "gate_events_ok": district_days_c >= 100,
        "gate_geocode_ok": share >= 0.60,
    }

    def table(series: pd.Series, header: str) -> str:
        lines = [f"| {header} | Events |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in series.items()]
        return "\n".join(lines)

    year = pos.assign(year=pd.to_datetime(pos["date"]).dt.year).groupby("year").size()
    by_type = frame.groupby("event_type").size().sort_values(ascending=False)
    by_level = pos_c.groupby("geocode_level").size()
    by_district = pos.groupby("district").size().sort_values(ascending=False)
    tehsil_counts = pos_c[pos_c["tehsil_id"].notna()].groupby("tehsil_id").size().sort_values(ascending=False)

    text = f"""# M1 report: PDMA flood event dataset

Built {dt.date.today().isoformat()} from {n_reports} cached reports (last report date {last_report}).
All figures are counts; the event file itself is private (`data/events/`, gitignored).

## Gate G1

| Check | Value | Threshold | Pass |
|---|---|---|---|
| Unique positive district-days, candidate districts | {district_days_c} | >= 100 | {"yes" if gate["gate_events_ok"] else "no"} |
| Positive events at tehsil level or better, candidate districts | {share:.0%} | >= 60% | {"yes" if gate["gate_geocode_ok"] else "no"} |

All KP: {len(pos)} positive events on {district_days} district-days.

## Events by type (all KP, after de-duplication)

{table(by_type, "Type")}

Positives = flash_flood, flood, cloudburst, drowning. Landslides and roof collapses are stored but are not positives.

## Positive events by year (all KP)

{table(year, "Year")}

## Positive events by district (all KP)

{table(by_district, "District")}

## Geocode level, positive events in candidate districts

{table(by_level, "Level")}

## Positive events per tehsil (candidate districts, top 25)

{table(tehsil_counts.head(25), "Tehsil")}

## Extraction notes

| Item | Count |
|---|---|
| LLM records (report x district) | {stats["llm_records"]} |
| LLM records with no incident | {stats["llm_no_incident"]} |
| Incident dates taken from text | {stats["date_ok"]} |
| Incident dates out of range, report date used | {stats["date_fallback"]} |
| Landslide rows from tables | {stats["table_landslide"]} |
| Collapse rows from tables | {stats["table_collapse"]} |
| Drafts before de-duplication | {stats["drafts"]} |
| Events after de-duplication | {len(frame)} |

Name safety: villages are stored only as gazetteer names; water-body strings with name markers are dropped; no free text is stored.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Hand-written sections (spot check, privacy notes) live below this marker and
    # are kept when the report is regenerated.
    if path.is_file():
        old = path.read_text(encoding="utf-8")
        if MANUAL_MARKER in old:
            text = text.rstrip() + "\n\n" + old[old.index(MANUAL_MARKER):]
    path.write_text(text, encoding="utf-8")
    return gate


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    data = settings.data_dir
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=data / "interim" / "pdma_llm")
    parser.add_argument("--raw-dir", type=Path, default=settings.raw_pdma_dir)
    parser.add_argument("--out-dir", type=Path, default=data / "events")
    parser.add_argument("--report", type=Path, default=Path("reports") / "m1_events_qa.md")
    args = parser.parse_args(argv)

    stats: Counter = Counter()
    geocoder = Geocoder(data / "reference")
    drafts = drafts_from_llm(args.cache_dir, geocoder, stats)
    drafts += drafts_from_tables(args.raw_dir, geocoder.names, stats)
    stats["drafts"] = len(drafts)
    events = to_events(deduplicate(drafts))
    events = apply_corrections(events, args.out_dir / "event_corrections.csv", stats)

    for e in events:  # final privacy check
        for value in (e.village, e.tehsil, e.water_body):
            if value and has_name_markers(value):
                raise RuntimeError(f"Name marker found in event {e.event_id}")

    frame = write_outputs(events, args.out_dir)
    write_spot_check(events, args.out_dir / "spot_check.csv")
    reports = sorted(args.raw_dir.glob("*.html.gz"))
    index = {}
    with (args.raw_dir / "_index.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("report_date"):
                index[rec["dsrid"]] = rec["report_date"]
    gate = write_qa(frame, stats, args.report, len(reports), max(index.values()) if index else "?")
    print(json.dumps({"events": len(frame), "positives": int(frame["is_positive"].sum()), **gate}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
