# Nigehban website

Next.js website for Nigehban. Light, warm design (off-white ground, charcoal type, black pill
buttons; colour only where it means risk). English (default) and Urdu (Nastaliq, right to left),
switched from the header and remembered per browser. Icons from lucide-react; subtle entrance motion
(`components/site/Motion.tsx`, off when the system asks for reduced motion). Works on desktop and phone.

## Pages

| Path | What it does |
|---|---|
| `/` | Home: "Where do you live?" search, outlook map with a plain summary sentence, how it works (4 icon steps), what the colours mean, what you can do here, emergency strip |
| `/map` | Full risk map: day and layer switches, counts, selected tehsil (levels, reasons, exposure, river flow, satellite rain), filterable ranked list |
| `/area` | My area: 4-day levels for a place, what to do, reasons, alerts sign-up, "Am I in a danger zone?" check with a walking route to higher ground, nearby safer places, Rescue 1122 and the district control room |
| `/ask` | Ask Nigehban: suggested questions, grounded answers with sources, Urdu voice playback |
| `/alerts` | Choose places, subscribe to the web inbox (and browser notifications), inbox, stop alerts, delete my data |
| `/safety` | Before / during / after guidance and emergency numbers |
| `/board` | Authority board (password): map, ranked table, tehsil detail, advisory drafts, replay switch |

The footer's **Demo: see a past flood** links switch every public page to a past day (14 Aug 2025
Buner, 26 Jun 2025 Swat) to show what Nigehban said the day before a real flood.

## Code

- `src/app/(site)/` public pages, sharing `layout.tsx` (header, footer, site state)
- `src/components/site/` header, footer, logo, icons, place search, level strip
- `src/lib/site.tsx` shared state (language, replay date, place, subscription) in localStorage
- `src/lib/copy.ts` page text in English and Urdu; `src/lib/i18n.ts` app strings
- `src/lib/hooks.ts` data hooks with a small cache; `src/components/RiskMap.tsx` MapLibre map

## Run locally

1. Start the API from the repo root: `python -m uvicorn backend.app.main:app --port 8000`
2. In `frontend/`: `npm install`, copy `.env.example` to `.env.local`, then `npm run dev`
3. Open http://localhost:3000 (website) and http://localhost:3000/board (board).

Browser notifications need `NEXT_PUBLIC_VAPID_PUBLIC_KEY` here and the VAPID key pair in the
backend `.env` (`python -m backend.app.alerts.channels --vapid`).

## Deploy (Vercel)

Root directory `nigehban/frontend`; set `NEXT_PUBLIC_API_URL` to the backend URL and add the
Vercel domain to the backend's `NIGEHBAN_CORS_ALLOW_ORIGINS`.
