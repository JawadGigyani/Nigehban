import datetime as dt
import gzip

import httpx

from pipelines.pdma import fetch_dsr as f

REPORT = "<html><td>No. PDMA/PEOC/DSR</td><span>Date: 15/08/2025</span>Buner Flash Flood</html>"
EMPTY = "<html><span>Date:</span><span></span></html>"


def _resp(status: int, text: str) -> httpx.Response:
    return httpx.Response(status, text=text, request=httpx.Request("GET", "http://pdma.test"))


def test_parse_report_date():
    assert f.parse_report_date(REPORT) == dt.date(2025, 8, 15)
    assert f.parse_report_date("Date: <b>6/7/2019</b>") == dt.date(2019, 7, 6)
    assert f.parse_report_date(EMPTY) is None
    assert f.parse_report_date("Date: 31/02/2025") is None


def test_run_caches_reports_and_resumes(tmp_path):
    pages = {1: _resp(200, REPORT), 2: _resp(500, EMPTY), 3: _resp(200, EMPTY)}
    calls: list[int] = []

    def fetcher(dsrid):
        calls.append(dsrid)
        return pages[dsrid]

    counts = f.run(1, 3, tmp_path, fetcher, interval_s=2.0, sleep=lambda s: None)
    assert counts == {"report": 1, "empty": 2, "error": 0, "skipped": 0}
    with gzip.open(f.cache_path(tmp_path, 1), "rt", encoding="utf-8") as fh:
        assert "15/08/2025" in fh.read()
    assert not f.cache_path(tmp_path, 2).exists()
    index = f.load_index(tmp_path)
    assert index[1].report_date == "2025-08-15" and index[2].http_status == 500

    calls.clear()
    counts = f.run(1, 3, tmp_path, fetcher, interval_s=2.0, sleep=lambda s: None)
    assert calls == [] and counts["skipped"] == 3


def test_errors_are_retried_on_next_run(tmp_path):
    state = {"fail": True}

    def fetcher(dsrid):
        if state["fail"]:
            raise httpx.ConnectError("down")
        return _resp(200, REPORT)

    counts = f.run(5, 5, tmp_path, fetcher, interval_s=1.0, sleep=lambda s: None)
    assert counts["error"] == 1
    state["fail"] = False
    counts = f.run(5, 5, tmp_path, fetcher, interval_s=1.0, sleep=lambda s: None)
    assert counts["report"] == 1
    assert f.load_index(tmp_path)[5].status == "report"


def test_gateway_errors_retry_within_fetch(tmp_path):
    replies = [_resp(503, ""), _resp(200, REPORT)]
    entry = f.fetch_one(9, lambda _: replies.pop(0), tmp_path, sleep=lambda s: None)
    assert entry.status == "report"


def test_polite_interval_is_respected(tmp_path):
    now = {"t": 0.0}
    sleeps: list[float] = []

    def sleep(s):
        sleeps.append(s)
        now["t"] += s

    f.run(1, 3, tmp_path, lambda _: _resp(200, EMPTY), interval_s=2.0,
          sleep=sleep, clock=lambda: now["t"])
    assert sleeps == [2.0, 2.0]  # no wait before the first request
