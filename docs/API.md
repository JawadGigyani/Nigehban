# API

JSON over HTTP. Locally at `http://127.0.0.1:8000`. Try every endpoint at **`/docs`**.

**Replays:** add `as_of`, for example `?as_of=2025-08-14T09:00:00+05:00`, to get the answer as it was
on that day.

**Limits:** 60 requests a minute per IP; chat 8 a minute and 1,500 a day in total.

## Endpoints

| Method | Path | What it returns | Access |
|:--|:--|:--|:--|
| GET | `/health` | `ok`, or `degraded` with missing data files | public |
| GET | `/risk` | Level for every tehsil, days 0–3 | public |
| GET | `/tehsils/{id}` | One tehsil: villages, safer places, Rescue 1122, rivers | public |
| GET | `/geo/tehsils` | Tehsil boundaries (GeoJSON) | public |
| GET | `/places/search?q=` | Villages, towns and tehsils (English or Urdu) | public |
| GET | `/rain/observed` | Satellite rain already fallen | public |
| POST | `/geo/check` | Is this point in danger, and what to do | public |
| POST | `/route/shelter` | Walking route to the nearest safer place | public |
| POST | `/chat` | Ask Nigehban | public |
| POST | `/subscriptions` | Subscribe to alerts | public |
| DELETE | `/subscriptions/{id}` | Stop alerts | public |
| POST | `/me/delete` | Delete all data for a contact | public |
| GET | `/inbox/{subscription_id}` | Alerts delivered to that subscription | public |
| POST | `/tts` | Urdu text to speech | public |
| GET | `/audio/{key}.mp3` | Saved voice note | public |
| GET | `/config` | `{"voice": true/false}` | public |
| POST | `/board/login` | Board token (12 hours) | password |
| GET | `/alerts` | Recent alerts | board token |
| POST | `/advisories/draft` | Printable advisory for up to 12 tehsils | board token |
| POST | `/internal/run-cycle` | Run the alert job | internal token |

Board endpoints need `Authorization: Bearer <token>`. The alert job needs `X-Internal-Token` when
`NIGEHBAN_ENVIRONMENT=production`.

## Examples

**Risk for every tehsil**

```http
GET /risk?as_of=2025-08-14T09:00:00+05:00
```

```json
{
  "issue_date": "2025-08-14",
  "replay": true,
  "tehsils": [{
    "tehsil_id": "swat__kabal", "tehsil": "Kabal", "district": "Swat",
    "max_level": "very_high",
    "days": [{"date": "2025-08-14", "lead_days": 0, "level": "very_high",
              "drivers": ["rain in the wettest part of the tehsil: 49 mm"]}]
  }]
}
```

Levels: `low`, `moderate`, `high`, `very_high`.

**Ask a question**

```http
POST /chat
{"message": "Is there flood risk in Swat tomorrow?", "as_of": "2025-08-14T09:00:00+05:00"}
```

```json
{
  "answer": "Yes. Babuzai, Swat has a very high flash-flood risk tomorrow…",
  "level": "very_high",
  "citations": [{"ref": "risk:swat__babuzai:2025-08-15", "label": "Nigehban risk model, 15 Aug"}],
  "checked": true,
  "fallback": false
}
```

`level` always comes from the model, never the AI. `checked` means the answer passed the evidence checks.

**Subscribe**

```http
POST /subscriptions
{"channel": "web_inbox", "address": "<device id>", "language": "ur", "tehsil_ids": ["buner__gagra"]}
```

The contact is stored encrypted and never returned.

**Check a point**

```http
POST /geo/check
{"lat": 34.79, "lon": 72.37}
```

Returns `advice` (`move_away`, `be_ready`, `stay_alert`, `normal`) with text in English and Urdu.
Returns `503` if terrain data isn't built, and `422` outside the covered area.
