# API

FastAPI backend, JSON over HTTP. Locally at http://127.0.0.1:8000; interactive docs with "Try it
out" at `/docs`. All times are Pakistan time (UTC+5) unless stated.

**Replays**: endpoints that take `as_of` (an ISO date-time, for example
`2025-08-14T09:00:00+05:00`) answer as if it were that moment, using the forecasts exactly as they
were issued then.

**Access**: public endpoints are rate limited per IP (60 requests per minute; `/chat` 8 per minute
and 1,500 per day in total). Board endpoints need `Authorization: Bearer <token>` from
`/board/login`. `/internal/run-cycle` needs the `X-Internal-Token` header in production.

## Risk and places

### `GET /health`
`{"status": "ok" | "degraded", "app", "version", "missing_data": [...]}`; `degraded` lists runtime
files that are missing.

### `GET /geo/tehsils`
GeoJSON of the in-scope tehsils (`tehsil_id`, names, district, centroid).

### `GET /risk?as_of=`
Risk for every tehsil, lead 0–3.

```json
{
  "issue_date": "2025-08-14", "replay": true, "generated_at": "...",
  "tehsils": [{
    "tehsil_id": "swat__kabal", "tehsil": "Kabal", "district": "Swat",
    "tehsil_ur": "کبل", "district_ur": "سوات",
    "max_level": "very_high", "max_probability": 0.031,
    "days": [{"date": "2025-08-14", "lead_days": 0, "level": "very_high", "probability": 0.031,
              "glofas_flag": false, "drivers": ["rain in the wettest part of the tehsil: 49 mm"],
              "driver_codes": ["precip_cell_max"]}]
  }]
}
```

Levels: `low`, `moderate`, `high`, `very_high`.

### `GET /tehsils/{tehsil_id}?as_of=`
Detail for one tehsil: `exposure` (`high`, `medium`, `low`, `villages`), `high_villages`,
`shelters` and `rescue_1122` (nearest first, with `km`, all unverified), `health`,
`rescue_1122_control_room` (district number), `rivers` (GloFAS series with the 2- and 5-year
flows), `note`.

### `GET /places/search?q=&limit=12`
Villages, towns and tehsils matching `q` (at least 2 characters, English or Urdu):
`[{"type": "village" | "tehsil", "id", "name", "tehsil_id", "tehsil", "label_ur", "lat", "lon"}]`.

### `GET /rain/observed?as_of=`
Satellite rain already fallen (NASA IMERG): latest finished day when live, the day before `as_of`
in a replay. `{"date", "run", "available", "note", "cell_size_deg": 0.1, "tehsils": [{"tehsil_id",
"mean_mm", "max_mm"}], "cells": [{"lon", "lat", "mm"}]}`. Observed only, not a forecast.

## Safety

### `POST /geo/check`
Request `{"lat", "lon", "as_of"?}`. Response: `tehsil_id`, `in_danger_zone`, `reasons`,
`level_today_tomorrow`, `river_flag`, `levels` (per lead), `advice` (`move_away`, `be_ready`,
`stay_alert`, `normal`), `advice_text` in `en`, `ur`, `ur_roman`, `note`. 422 outside the covered area.

### `POST /route/shelter`
Request `{"lat", "lon", "mode": "walk" | "drive"}`. Response: `engine`, `destination` (`kind`,
`name`, `lat`, `lon`), `distance_m`, `duration_min`, `geometry` (GeoJSON LineString),
`low_ground_share`, `notes`. 404 if nothing within 12 km.

## Ask Nigehban

### `POST /chat`
Request:

```json
{"message": "کیا کل سوات میں سیلاب کا خطرہ ہے؟", "session_id": null, "language": null,
 "tehsil_id": null, "lat": null, "lon": null, "as_of": null}
```

Response: `session_id`, `answer`, `actions` (`text`, `refs`), `language`, `intent`, `tehsil_id`,
`place`, `level` (from the model, never the LLM), `citations` (`ref`, `label`, `kind`), `checked`
(passed the grounding checks), `fallback` (template answer used).

## Alerts and subscriptions

### `POST /subscriptions`
Request `{"channel": "web_inbox", "address", "language": "ur" | "en" | "ur_roman", "tehsil_ids": [],
"village_ids": []}`. `address` is the browser's random device id. Returns the subscription without the
contact. (`console` is also accepted, for local testing.)

### `DELETE /subscriptions/{id}`
Removes the subscription and its delivery records.

### `POST /me/delete`
Request `{"address"}`. Deletes every subscription and delivery for that contact.

### `GET /inbox/{subscription_id}`
`{"language", "alerts": [{"id", "tehsil_id", "level", "valid_date", "issued_at", "lead_days",
"message", "replay", "audio_url", "citations"}]}`.

### `POST /internal/run-cycle`
Header `X-Internal-Token`. Request `{"as_of"?, "deliver": true}`. Runs one alert cycle:
`{"issued_for", "replay", "candidates", "new_alerts", "skipped_duplicates", "deliveries_ok",
"deliveries_failed"}`. The same cycle runs from `python -m pipelines.alerts.run_cycle`.

## Board (token)

### `POST /board/login`
Request `{"password"}` (checked against `NIGEHBAN_BOARD_PASSWORD`). Returns `{"token",
"expires_at"}`, valid for 12 hours.

### `GET /alerts?limit=50&replay=`
Recent alerts with level, date, lead, reasons and how many subscribers received them.

### `POST /advisories/draft`
Request `{"tehsil_ids": [...] (1–12), "as_of"?}`. Returns an advisory: `title`, `date`, `area`,
`risk` (levels per tehsil and day), `actions` (checked against the evidence), `public_message_en`,
`public_message_ur`, `sources`, `footer`, `checked`, `markdown`.

## Voice and config

### `POST /tts`
Request `{"text"}` in Urdu. Returns `{"audio_url"}` (ElevenLabs, cached).

### `GET /audio/{key}.mp3`
Cached audio for alerts and answers.

### `GET /config`
What the website may turn on, without secrets: `{"voice": true | false}`.
