# Nigehban web app

Next.js app with two parts:

- `/` citizen app (mobile-first, installable PWA). Urdu (Nastaliq, right to left) by default,
  English and Roman Urdu toggle. Tabs: risk for my place (today and the next 3 days, reasons,
  nearest safer places and Rescue 1122, all marked unverified), alerts (subscribe, in-app inbox,
  optional browser notifications), ask (grounded Q&A), my data (language, demo replay, stop
  alerts, delete all my data).
- `/board` authority board (English, password login): tehsil map coloured by level for the
  chosen day, ranked table with reasons, tehsil detail (exposure, high-exposure villages,
  shelters and higher ground, Rescue 1122, river flow), alerts sent, replay switch (live,
  14 Aug 2025, 26 Jun 2025, or any date from 1 Mar 2024).

## Run locally

1. Start the API from the repo root: `python -m uvicorn backend.app.main:app --port 8000`
2. In `frontend/`: `npm install`, copy `.env.example` to `.env.local`, then `npm run dev`
3. Open http://localhost:3000 (citizen) and http://localhost:3000/board (board).

Browser notifications need `NEXT_PUBLIC_VAPID_PUBLIC_KEY` here and the VAPID key pair in the
backend `.env` (`python -m backend.app.alerts.channels --vapid`).

## Deploy (Vercel)

Root directory `nigehban/frontend`; set `NEXT_PUBLIC_API_URL` to the backend URL and add the
Vercel domain to the backend's `NIGEHBAN_CORS_ALLOW_ORIGINS`.
