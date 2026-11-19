# M8 agent: sample answers

Generated 2026-11-19 by `python -m pipelines.agent.sample_answers` (live LLM, Groq with key and
model rotation; Gemini as fallback).

## How the agent works

LangGraph flow: understand (intent, language, place, day, English search query) → locate (gazetteer,
manual places, tehsil names, or the user's tehsil / location) → gather evidence → compose → validate.

Evidence items each have an id: `risk:` (model level per day and its reasons), `exposure:` (terrain bands),
`facility:` (nearest shelters, higher ground, Rescue 1122, health; unverified), `doc:` (passages from PDMA,
NDMA and NIH guidance), `contact:helplines`.

Checks in code, not left to the model:
- every cited id must exist in the evidence; actions need at least one id;
- the level stated must equal the model's level for the day asked about; with no risk evidence, no level;
- up to 2 retries with the reason for rejection; then a template answer built only from the evidence;
- the closing line "Follow PDMA and district administration instructions" is added in the user's language;
- Urdu script in the message means an Urdu reply; Urdu in Latin letters means Roman Urdu.

Knowledge base: 9 graph nodes; passages from 6 official documents,
BM25 search (no embedding API), name lists from committee pages removed.

## Samples

### کل پیر بابا میں سیلاب کا کتنا خطرہ ہے؟

Replay as of: 14 Aug 2025 09:00 PKT

- Language: ur · intent: risk · place: Pir Baba (Gagra tehsil (Buner district))
- Level (from the model): high · passed checks: True (attempts 1, fallback False) · 16.6 s

**Answer**

کل پیر بابا (گرا، بنوں) میں سیلاب کا خطرہ زیادہ ہے۔ بارش اور گیلے مٹی کے باعث فلیش‑فلوڈ کا امکان بہت زیادہ ہے۔ اگر آپ کو خطرہ محسوس ہو تو فوری طور پر اونچی جگہ پر جائیں اور مقامی ہیلپ لائن 1122 یا 1700 پر رابطہ کریں۔

پی ڈی ایم اے اور ضلعی انتظامیہ کی ہدایات پر عمل کریں۔

**Actions**

  - قریبی اونچی جگہ یا ہائی گراؤنڈ پر منتقل ہوں۔
  - قریبی غیر تصدیق شدہ پناہ گاہیں جیسے مدینہ مسجد (تقریباً 2.9 km) یا نامعلوم یونیورسٹی (تقریباً 6.6 km) پر جائیں۔ (پناہ گاہوں کی تصدیق نہیں ہوئی)
  - ایمرجنسی مدد کے لیے ریسکیو 1122 (ڈگر، تقریباً 9.2 km) یا PDMA ہیلپ لائن 1700 پر کال کریں۔ (موقع کی تصدیق نہیں ہوئی)
  - مقامی ریڈیو یا ٹی وی پر تازہ ترین اطلاعات کے لیے سنیں۔

**Citations**

  - `risk:buner__gagra:2025-08-14`: Nigehban risk model, 14 Aug
  - `facility:osm:n13371507871`: OpenStreetMap / Nigehban (unverified)
  - `facility:osm:w696103141`: OpenStreetMap / Nigehban (unverified)
  - `facility:manual:rescue1122:buner:daggar`: OpenStreetMap / Nigehban (unverified)
  - `contact:helplines`: Rescue 1122; PDMA helpline
  - `doc:pdma_flood_dos_donts:p1#1`: PDMA (pdma.gov.pk), Flood: Do's and Don'ts, p. 1

### Is there a safe place near Mingora if the river rises tomorrow?

Replay as of: 14 Aug 2025 09:00 PKT

- Language: en · intent: safety_advice · place: Mingora (Babuzai tehsil (Swat district))
- Level (from the model): very_high · passed checks: True (attempts 1, fallback False) · 2.3 s

**Answer**

The flash‑flood risk for Mingora (Babuzai tehsil) tomorrow is very high. Seek higher ground immediately and move to the nearest safe shelter such as Gali Dabba Masjid (about 0.2 km away) or the nearby places of worship (0.5–0.8 km away). Call Rescue 1122 for assistance and keep the PDMA helpline (1700) handy.

Follow PDMA and district administration instructions.

**Actions**

  - Go to Gali Dabba Masjid, about 0.2 km from Mingora (unverified shelter).
  - If Gali Dabba Masjid is full, use the unnamed place of worship 0.5 km away (unverified shelter).
  - Call Rescue 1122 Saidu Sharif (≈1.5 km away) for evacuation help (unverified).
  - Dial the PDMA helpline 1700 for further guidance.

**Citations**

  - `risk:swat__babuzai:2025-08-15`: Nigehban risk model, 15 Aug
  - `facility:osm:n5186531975`: OpenStreetMap / Nigehban (unverified)
  - `facility:osm:n4927220123`: OpenStreetMap / Nigehban (unverified)
  - `facility:manual:rescue1122:swat:saidu_sharif`: OpenStreetMap / Nigehban (unverified)
  - `contact:helplines`: Rescue 1122; PDMA helpline

### Kalam mein mavishi ka kya karein agar selab aaye?

Replay as of: 14 Aug 2025 09:00 PKT

- Language: ur_roman · intent: safety_advice · place: Kalam (Kalam tehsil (Swat district))
- Level (from the model): low · passed checks: True (attempts 1, fallback False) · 2.3 s

**Answer**

Kalam mein aaj flash-flood ka risk kam (low) hai. Phir bhi, agar barish ke baad paani behna shuru ho jaye to foran unche ilaqe ki taraf rukh karein. Apne ghar ki cheezein upar ki manzilon par rakhein, bijli ke switch band kar dein aur zaroori samaan le kar nikal jayein. Agar aapko madad ki zarurat ho to Rescue 1122 ko 1122 dial karein.

PDMA aur zilai intezamia ki hidayat par amal karein.

**Actions**

  - Usharan (takreeban 1.9 km door) ya Matiltan (9.3 km) ya Bandi (19.8 km) ja kar unche zameen par pahunchain (unverified).
  - Agar zarurat ho to Rescue 1122 Bahrain (31 km door) ko 1122 dial karein (unverified).
  - PDMA ke flood do's and don'ts follow karein: turant unche zameen par chalein, utilities band karein, aur paani mein bijli ke saamaan ko haath na lagayein.

**Citations**

  - `risk:swat__kalam:2025-08-14`: Nigehban risk model, 14 Aug
  - `facility:high_ground:gn:1481730`: OpenStreetMap / Nigehban (unverified)
  - `facility:high_ground:osm:n2948990458`: OpenStreetMap / Nigehban (unverified)
  - `facility:high_ground:gn:1478326`: OpenStreetMap / Nigehban (unverified)
  - `facility:manual:rescue1122:swat:bahrain`: OpenStreetMap / Nigehban (unverified)
  - `doc:pdma_flood_dos_donts:p1#2`: PDMA (pdma.gov.pk), Flood: Do's and Don'ts, p. 1

### Is tap water safe to drink after a flood?

Live

- Language: en · intent: safety_advice · place: none
- Level (from the model): none · passed checks: True (attempts 1, fallback False) · 11.2 s

**Answer**

Tap water may be contaminated after a flood and should not be drunk untreated. Boil it for at least one minute, use bottled water, or disinfect it before consumption. Follow health officials' guidance on water safety.

Follow PDMA and district administration instructions.

**Actions**

  - Boil tap water for at least one minute before drinking.
  - If possible, use bottled or treated water for drinking and cooking.
  - Check updates from local health officials or PDMA for safe water advisories.

**Citations**

  - `doc:nih_flood_guidelines:p6#4`: National Institute of Health, Islamabad, Guidelines on Floods (health), p. 6

### Who won the cricket match yesterday?

Live

- Language: en · intent: small_talk · place: none
- Level (from the model): none · passed checks: True (attempts 1, fallback False) · 10.7 s

**Answer**

I’m here to provide flash‑flood risk updates, safety advice, and information on nearby shelters and Rescue 1122 services for places in northern Khyber Pakhtunkhwa. Which location would you like to check?

**Actions**

  - none

**Citations**

  - none
