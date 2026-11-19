# M10 + M11 + F11: route to safety, danger-zone check, advisory draft

Built 20 Nov 2026.

## M10: route to a safer place (`POST /route/shelter`)

- Engines: OpenRouteService when `NIGEHBAN_ORS_API_KEY` is set (free key), otherwise a built-in router
  (networkx) on OpenStreetMap roads and paths.
- Roads: cut once from the Geofabrik Pakistan extract (`python -m pipelines.reference.extract_roads`,
  158 MB download, kept private) into 793 tiles of 0.1° (20 MB). The public Overpass servers were
  overloaded during the build ("at capacity"), so the router no longer depends on them.
- Segments on low ground beside streams (HAND under 3 m) cost five times more: routes prefer higher
  roads but can still cross bridges. Destinations: nearest shelters and higher ground not in the
  high-exposure band (unverified, and the answer says so).

| From | Mode | Result |
|---|---|---|
| Mingora bypass, riverside | walk | university building, 2.3 km, about 35 min, none on low ground |
| Pir Baba | walk | Madinah Masjid, 5.1 km; nearest mapped path 820 m away (OSM sparse) |
| Kalam | drive | higher ground at Usharan, 5.1 km, about 13 min |

## M11: danger-zone check (`POST /geo/check`)

- In the zone when the lowest ground within about 100 m is under 3 m above the stream and a river
  draining at least 50 km² is within about 150 m, or at a riverside picnic or tourist spot (OSM).
- Advice from the zone and the model's level (today and tomorrow): high or very high → move away;
  moderate → be ready; otherwise stay alert (in zone) or normal. The river flag alone counts as
  moderate. Text in Urdu, English and Roman Urdu.
- Terrain: 30 m in Swat, 90 m elsewhere; a new raster of each stream's upstream area was added.

**Done-when check** (Mingora bypass, 34.7937 N 72.3720 E, about 90 m from the Swat River):

| Date | Level | Advice |
|---|---|---|
| 14 Aug 2025 (replay) | very high | **move away** |
| 25 Jun 2025 (replay) | moderate | be ready |
| 20 Nov 2026 (live) | low | stay alert |

A point in Mingora town about 1.6 km from the river gives "normal". Note: the Copernicus elevation
model is a surface model (buildings and trees included), so dense riverside towns can look higher
than the ground is; the check is a guide, and the app says so.

## F11: advisory draft (`POST /advisories/draft`, board login)

- Layout: title, date, area, risk table, recommended actions, message for the public, sources,
  "DRAFT FOR OFFICIAL REVIEW".
- Written by code: title, date, area, the risk table and the risk sentence of the public message
  (levels and Urdu place names come from the model and the fixed names table), sources, footer.
- Written by the LLM: actions (each citing evidence) and the advice part of the public message.
  Rejected and retried when it cites unknown evidence, states risk levels, misspells an Urdu tehsil
  name, puts Urdu script in the English text, or presents floods as certain ("expected", "will hit").
- Board: "Draft advisory for high-risk tehsils" (up to 12) and "Draft advisory for this tehsil";
  the draft opens in a window with Copy and Print.

## Web app

- Citizen Risk tab: "Am I in a danger zone?" (phone location or the chosen place), advice in the
  user's language, route to a safer place with distance, walking time and an "open in map" link.
- Fizagat is now placed on the Mingora bypass riverbank (it was 2.5 km from the river).

## Checked in the browser

Citizen app (Urdu, 14 Aug 2025 replay, Fizagat): "move away now", very high, route 2.3 km / 35 min.
Board (14 Aug 2025 replay): advisory for 12 high-risk tehsils with checked actions, correct Urdu names.

## Limits

- ORS needs a free key (optional; the built-in router works without it).
- Roads and shelters come from OpenStreetMap, which is thin in rural KP; routes can start far from a
  mapped path, and the app says so.
