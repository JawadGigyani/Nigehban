# Nigehban website

Next.js 15 website and authority board. English and Urdu (right to left), desktop and phone.

## Run

```bash
npm install
npm run dev        # http://localhost:3000
npm test           # 13 tests (Vitest)
```

Needs the API running on port 8000 (set `NEXT_PUBLIC_API_URL` in `.env.local` to change it).

## Pages

| Path | Page |
|:--|:--|
| `/` | Home: search, outlook map, how it works |
| `/map` | Risk map with every tehsil ranked |
| `/area` | One place: levels, advice, danger check, safer places |
| `/ask` | Ask Nigehban |
| `/alerts` | Subscribe and read alerts |
| `/safety` | Safety guide and emergency numbers |
| `/board` | Authority board (password) |

## Code

| Path | Contains |
|:--|:--|
| `src/app/(site)/` | Public pages and their shared layout |
| `src/app/board/` | Authority board |
| `src/components/` | Map, header, footer, search, icons |
| `src/lib/` | API client, shared state, English and Urdu text, tests |

## Design notes

- Colour is used only for risk levels; everything else stays neutral.
- Sections fade in on scroll. With the system's reduced-motion setting, only gentle fades remain.
- If a browser can't start the map (no WebGL), a short message replaces it; the rest still works.
- Shareable links: `?replay=2025-08-14`, `?tehsil=swat__kabal`, `?lang=ur`.
