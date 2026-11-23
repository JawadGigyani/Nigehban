# M9 alert engine: replay of 13–15 Aug 2025

Generated 2026-11-19 by `python -m pipelines.alerts.replay_cycle` (separate replay database,
archived forecasts, the shipped model and forecast-tuned levels). Rule: level high or above at lead ≤ 2
days, or the river flag; one alert per tehsil, level and date; a repeat only if the level rises.

## Done-when check

| Check | Result |
|---|---|
| Buner alerts produced | 9 (buner__daggar 2025-08-15 very_high, buner__gagra 2025-08-14 high, buner__gagra 2025-08-15 high, buner__gagra 2025-08-15 very_high, buner__khado_khel 2025-08-14 high, buner__khado_khel 2025-08-15 high, buner__mandanr 2025-08-14 high, buner__mandanr 2025-08-15 high, buner__mandanr 2025-08-15 very_high) |
| Duplicate alerts (same tehsil, level, date) | 0 |
| Same tehsil and date sent again only because the level rose | 14 |
| Buner alerts delivered on console | True |
| Delivered to a web inbox | True |

## Runs

| run (PKT) | candidates | new alerts | skipped (already sent) | deliveries ok | failed |
|---|---|---|---|---|---|
| 13 Aug 09:00 | 41 | 41 | 0 | 4 | 0 |
| 14 Aug 09:00 | 51 | 21 | 30 | 2 | 0 |
| 14 Aug 15:00 | 51 | 0 | 51 | 0 | 0 |
| 15 Aug 06:00 | 36 | 18 | 18 | 5 | 0 |

The second run on 14 Aug (15:00) repeats the 09:00 run: everything is skipped as already sent.

## Alerts

| tehsil | valid date | level | lead days | issued (UTC) | text checked | sent to |
|---|---|---|---|---|---|---|
| bajaur__utman_khel | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| battagram__batagram | 2025-08-14 | high | 0 | 14 Aug 04:00 | True | 0 |
| buner__gagra | 2025-08-14 | high | 0 | 14 Aug 04:00 | True | 2 |
| buner__khado_khel | 2025-08-14 | high | 0 | 14 Aug 04:00 | True | 0 |
| buner__mandanr | 2025-08-14 | high | 0 | 14 Aug 04:00 | True | 0 |
| lower_dir__adenzai | 2025-08-14 | very_high | 1 | 13 Aug 04:00 | True | 0 |
| lower_dir__balambat | 2025-08-14 | very_high | 1 | 13 Aug 04:00 | True | 0 |
| lower_dir__lalqila | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| lower_dir__lalqila | 2025-08-14 | very_high | 0 | 14 Aug 04:00 | True | 0 |
| lower_dir__munda | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| lower_dir__samarbagh | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| lower_dir__timergara | 2025-08-14 | very_high | 1 | 13 Aug 04:00 | True | 0 |
| malakand__bat_khela | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| mansehra__baffa_pakhal | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| mansehra__baffa_pakhal | 2025-08-14 | very_high | 0 | 14 Aug 04:00 | True | 0 |
| mansehra__mansehra | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| mansehra__mansehra | 2025-08-14 | very_high | 0 | 14 Aug 04:00 | True | 0 |
| shangla__alpuri | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| shangla__alpuri | 2025-08-14 | very_high | 0 | 14 Aug 04:00 | True | 0 |
| shangla__bisham | 2025-08-14 | high | 0 | 14 Aug 04:00 | True | 0 |
| shangla__chakisar | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| shangla__martoong | 2025-08-14 | high | 0 | 14 Aug 04:00 | True | 0 |
| shangla__puran | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| swat__babuzai | 2025-08-14 | very_high | 1 | 13 Aug 04:00 | True | 1 |
| swat__barikot | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| swat__barikot | 2025-08-14 | very_high | 0 | 14 Aug 04:00 | True | 0 |
| swat__charbagh | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| swat__kabal | 2025-08-14 | very_high | 1 | 13 Aug 04:00 | True | 0 |
| swat__khwaza_khela | 2025-08-14 | high | 0 | 14 Aug 04:00 | True | 0 |
| swat__matta_kharirai | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| swat__matta_kharirai | 2025-08-14 | very_high | 0 | 14 Aug 04:00 | True | 0 |
| swat__matta_sebujni | 2025-08-14 | high | 0 | 14 Aug 04:00 | True | 0 |
| upper_dir__dir | 2025-08-14 | high | 1 | 13 Aug 04:00 | True | 0 |
| upper_dir__khall | 2025-08-14 | very_high | 1 | 13 Aug 04:00 | True | 0 |
| upper_dir__wari | 2025-08-14 | very_high | 1 | 13 Aug 04:00 | True | 0 |
| bajaur__mamund | 2025-08-15 | high | 0 | 15 Aug 01:00 | True | 0 |
| bajaur__salarzai | 2025-08-15 | high | 0 | 15 Aug 01:00 | True | 0 |
| battagram__batagram | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 0 |
| buner__daggar | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 1 |
| buner__gagra | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 2 |
| buner__gagra | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 2 |
| buner__khado_khel | 2025-08-15 | high | 1 | 14 Aug 04:00 | True | 0 |
| buner__mandanr | 2025-08-15 | high | 1 | 14 Aug 04:00 | True | 0 |
| buner__mandanr | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 0 |
| lower_dir__adenzai | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 0 |
| lower_dir__balambat | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 0 |
| lower_dir__balambat | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 0 |
| lower_dir__lalqila | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 0 |
| lower_dir__samarbagh | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 0 |
| lower_dir__timergara | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 0 |
| malakand__bat_khela | 2025-08-15 | high | 0 | 15 Aug 01:00 | True | 0 |
| mansehra__baffa_pakhal | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 0 |
| mansehra__bala_kot | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 0 |
| mansehra__mansehra | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 0 |
| shangla__alpuri | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 0 |
| shangla__bisham | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 0 |
| shangla__bisham | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 0 |
| shangla__chakisar | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 0 |
| shangla__makhuzai | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 0 |
| shangla__martoong | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 0 |
| shangla__martoong | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 0 |
| shangla__puran | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 0 |
| swat__babuzai | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 1 |
| swat__bahrain | 2025-08-15 | high | 0 | 15 Aug 01:00 | True | 0 |
| swat__barikot | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 0 |
| swat__barikot | 2025-08-15 | very_high | 1 | 14 Aug 04:00 | True | 0 |
| swat__charbagh | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 0 |
| swat__charbagh | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 0 |
| swat__kabal | 2025-08-15 | very_high | 2 | 13 Aug 04:00 | True | 0 |
| swat__khwaza_khela | 2025-08-15 | high | 1 | 14 Aug 04:00 | True | 0 |
| swat__matta_kharirai | 2025-08-15 | very_high | 1 | 14 Aug 04:00 | True | 0 |
| swat__matta_sebujni | 2025-08-15 | high | 1 | 14 Aug 04:00 | True | 0 |
| upper_dir__dir | 2025-08-15 | very_high | 0 | 15 Aug 01:00 | True | 0 |
| upper_dir__khall | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 0 |
| upper_dir__larjam | 2025-08-15 | high | 0 | 15 Aug 01:00 | True | 0 |
| upper_dir__wari | 2025-08-15 | high | 2 | 13 Aug 04:00 | True | 0 |
| upper_dir__wari | 2025-08-15 | very_high | 1 | 14 Aug 04:00 | True | 0 |
| swat__babuzai | 2025-08-16 | high | 1 | 15 Aug 01:00 | True | 1 |
| swat__kabal | 2025-08-16 | high | 1 | 15 Aug 01:00 | True | 0 |
| swat__babuzai | 2025-08-17 | high | 2 | 15 Aug 01:00 | True | 1 |

## Sample Buner alerts

**buner__gagra, 2025-08-14, high**

- EN: Gagra, Buner – 14 Aug 2025 – Risk: high. Heavy rain (26 mm today, 30 mm in 3 days) and wet topsoil (0.34 m³/m³) raise flash‑flood danger. Move immediately to higher ground, avoid streams and nullahs, keep livestock away from the river. If safe, seek shelter at Madinah Masjid or the nearby university. Call Rescue 1122 for help.
Follow PDMA and district administration instructions.
- UR: گاگرہ، بونیر – ۱۴ اگست ۲۰۲۵ – خطرہ: زیادہ۔ شدید بارش (۲۶ ملی میٹر آج، ۳۰ ملی میٹر ۳ دنوں میں) اور گیلے اوپر کی مٹی (۰.۳۴ م³/م³) سے فلیش‑فلوڈ کا خطرہ بڑھ گیا ہے۔ فوراً بلند جگہ پر جائیں، نالوں اور دریاؤں سے بچیں، جانوروں کو دریا سے دور رکھیں۔ اگر محفوظ ہو تو مدینہ مسجد یا قریبی یونیورسٹی میں پناہ لیں۔ مدد کے لیے ۱۱۲۲ ڈائل کریں۔
پی ڈی ایم اے اور ضلعی انتظامیہ کی ہدایات پر عمل کریں۔
- Roman: Gagra, Buner – 14 August 2025 – Khatarah: zyada. Shiddat barish (26 mm aaj, 30 mm 3 dinon mein) aur gile oopar ki miti (0.34 m³/m³) se flash-flood ka khatra barh gaya hai. Furan buland jagah par jayein, nullon aur daryao se bachain, janwaron ko darya se door rakhein. Agar mehfooz ho to Madinah Masjid ya qareebi university mein panah lein. Madad ke liye 1122 dial karein.
PDMA aur zilai intezamia ki hidayat par amal karein.
- Citations: risk:buner__gagra:2025-08-14, exposure:tehsil:buner__gagra, facility:osm:n13371507871, facility:osm:w696103144, doc:pdma_flood_dos_donts:p1#2, contact:helplines

**buner__khado_khel, 2025-08-14, high**

- EN: Khado Khel, Buner – 14 Aug 2025 – high risk. Heavy rain (30 mm) and wet topsoil (0.34 m³/m³) forecast. Move immediately to higher ground such as Chinglai or Mughdara if safe. Avoid streams and nullahs. Call Rescue 1122 for help.
Follow PDMA and district administration instructions.
- UR: خدو خیل، بونیر – 14 اگست 2025 – زیادہ خطرہ۔ بارش (30 ملی میٹر) اور گیلے ٹاپسور (0.34 م³/م³) کی پیش گوئی۔ فوری طور پر بلند جگہ جیسے چنگلا یا مغدرا جائیں اگر محفوظ ہو۔ نلوں اور نالوں سے بچیں۔ مدد کے لیے 1122 ڈائل کریں۔
پی ڈی ایم اے اور ضلعی انتظامیہ کی ہدایات پر عمل کریں۔
- Roman: Khado Khel, Buner – 14 August 2025 – zyada khatra. Barish (30 mm) aur gile topsoil (0.34 m³/m³) ki paish goi. Fawri tor par buland jagah jaise Chinglai ya Mughdara jaen agar mehfooz ho. Nalon aur nullon se bachain. Madad ke liye 1122 dial karein.
PDMA aur zilai intezamia ki hidayat par amal karein.
- Citations: risk:buner__khado_khel:2025-08-14, facility:high_ground:osm:n4809773228, facility:high_ground:osm:n8883973195, doc:pdma_flood_dos_donts:p1#2

## Subscribers in this replay

Three demo subscriptions (contacts are demo strings, stored encrypted): Buner Gagra and Daggar on the
console in Urdu; Pir Baba (village, Gagra) in the web inbox in English; Swat Babuzai in the web inbox
in Roman Urdu.
