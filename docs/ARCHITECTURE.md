# Architecture

One Python API serves everything. The website calls it over HTTP. An alert job runs on a schedule.

```mermaid
flowchart LR
    subgraph SRC["Outside data"]
        OM["Open-Meteo<br/>forecasts · ERA5 · GloFAS"]
        NASA["NASA IMERG<br/>satellite rain"]
        LLM["Groq · Gemini<br/>language models"]
        EL["ElevenLabs<br/>Urdu voice"]
    end

    subgraph API["FastAPI backend"]
        H["hydromet<br/>weather per tehsil"]
        R["risk<br/>model and levels"]
        G["geo<br/>danger check · routes"]
        AG["agent<br/>Ask Nigehban"]
        AL["alerts<br/>rules · messages"]
        DB[("database<br/>SQLite / Postgres")]
    end

    subgraph WEB["Next.js website"]
        SITE["Public pages"]
        BOARD["Authority board"]
    end

    OM --> H --> R
    NASA --> H
    R --> AG
    R --> AL
    R --> SITE
    R --> BOARD
    G --> SITE
    LLM --> AG
    LLM --> AL
    EL --> AL
    AL --> DB --> SITE

    classDef src fill:#334155,stroke:#94a3b8,color:#ffffff
    classDef api fill:#0e5e66,stroke:#5eead4,color:#ffffff
    classDef web fill:#9a3412,stroke:#fdba74,color:#ffffff
    class OM,NASA,LLM,EL src
    class H,R,G,AG,AL,DB api
    class SITE,BOARD web
    style SRC fill:transparent,stroke:#94a3b8,stroke-dasharray:4 4
    style API fill:transparent,stroke:#5eead4,stroke-dasharray:4 4
    style WEB fill:transparent,stroke:#fdba74,stroke-dasharray:4 4
```

## The parts

| Part | Folder | What it does |
|:--|:--|:--|
| **Hydromet** | `backend/app/hydromet/` | Fetches forecasts, turns them into daily numbers per tehsil, tracks rivers and satellite rain |
| **Risk** | `backend/app/risk/` | Scores each tehsil and day, picks the level, explains why |
| **Geo** | `backend/app/geo/` | Danger check from terrain, walking routes, Rescue 1122 contacts, Urdu place names |
| **Agent** | `backend/app/agent/` | Answers questions from evidence and checks each answer |
| **Knowledge** | `backend/app/knowledge/` | Searchable PDMA, NDMA and NIH guidance |
| **Alerts** | `backend/app/alerts/` | Alert rules, messages in three languages, voice, advisories |
| **LLM** | `backend/app/llm/` | Language-model access with key rotation and fallback |
| **API** | `backend/app/api/` | HTTP endpoints ([API reference](API.md)) |
| **Website** | `frontend/` | Public pages and the authority board |
| **Pipelines** | `pipelines/` | Offline jobs that build data and train the model ([Data](DATA.md)) |

## How a risk level is made

```mermaid
flowchart LR
    A["Forecasts<br/>3 models"] --> B["Daily numbers<br/>per tehsil"]
    B --> C["Probability<br/>per model"]
    C --> D["Average"]
    D --> E["Level<br/>fixed thresholds"]
    E --> F["Reasons<br/>top drivers"]

    classDef step fill:#0e5e66,stroke:#5eead4,color:#ffffff
    class A,B,C,D,E,F step
```

1. Forecasts from ECMWF, GFS and ICON are fetched for every 0.25° cell and averaged per tehsil.
2. Each model's numbers are scored separately; the three probabilities are averaged.
3. Fixed thresholds per lead day turn the probability into Low, Moderate, High or Very high.
4. The inputs that pushed the score up the most become the reasons shown to people.
5. A high river forecast (GloFAS) adds a river flag. It can trigger an alert but never lowers a level.

**Replays** use the forecasts exactly as they were issued on that day, so they never see the future.

## How an alert is sent

1. The alert job runs (`python -m pipelines.alerts.run_cycle`, or `POST /internal/run-cycle`).
2. It picks tehsils at **High or above within 2 days**, or with a river flag.
3. It skips tehsils nobody has subscribed to, and anything already sent.
4. A language model writes the message in English, Urdu and Roman Urdu. Code checks the level,
   place and date. If the check fails, a template is used.
5. The Urdu message becomes a voice note.
6. The alert lands in each subscriber's web inbox.

Other channels (SMS, WhatsApp, push, a mobile app) can be added as one class each in
`backend/app/alerts/channels.py`.

## How a question is answered

```mermaid
flowchart LR
    Q["Question"] --> U["Understand<br/>intent · place · day"]
    U --> L["Locate<br/>tehsil or village"]
    L --> G["Gather evidence<br/>risk · places · guidance"]
    G --> C["Compose answer"]
    C --> V{"Checks pass?"}
    V -- yes --> OK["Answer with sources"]
    V -- "no, retry up to 2x" --> C
    V -- still no --> T["Safe template answer"]

    classDef step fill:#0e5e66,stroke:#5eead4,color:#ffffff
    classDef end_ fill:#9a3412,stroke:#fdba74,color:#ffffff
    class Q,U,L,G,C,V step
    class OK,T end_
```

The checks: every cited source must exist, the stated level must match the model, and Urdu place names
come from a fixed table. Urdu answers go to Gemini first, which writes better Urdu.

## Key decisions

| Decision | Why |
|:--|:--|
| **Tehsil, not house** | The weather grid is about 25 km; per-house risk would claim precision the data doesn't support. |
| **Simple model** | With 89 flood days, tree models overfit. Logistic regression generalised best. |
| **Levels from thresholds, never the AI** | Warnings must be reproducible. The AI only writes words. |
| **Three weather models** | They disagree on local storms; the average is steadier. |
| **Satellite rain as a layer only** | It helps only after rain has fallen, so it can't forecast. |
| **Named safer places only** | Nobody can find "an unnamed building". |
| **Free services** | Runs without a budget; a pacer and caches stay inside free limits. |
