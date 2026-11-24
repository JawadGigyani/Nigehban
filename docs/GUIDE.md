# User guide

A 15-minute tour of every feature. Start the app first ([Quick start](../README.md#quick-start)),
then open http://localhost:3000.

> [!TIP]
> Live risk is mostly Low outside the monsoon. For a real example, use **replay mode**: click the
> **Live** pill in the header and pick **14 Aug 2025 · Buner cloudburst**. Every page then shows the
> forecast exactly as it was issued the day before that flood.

## 1. Home

- **Search** a village, town or tehsil (try *Mingora*, *Daggar*, *Kalam*) to open its page.
- **Map:** switch days with *Today / Tomorrow / …*. Click any tehsil for its card.
- **Satellite rain:** shows rain NASA measured on the day before.
- On the replay day, about 12 tehsils are **Very high** for 15 Aug.

## 2. My area

Shows one place in detail:

| Section | What you see |
|:--|:--|
| **Outlook** | Four day cards, coloured by level |
| **What to do** | Advice that matches the level |
| **Why** | The reasons, in plain words |
| **Am I in a danger zone?** | Checks a point; offers a walking route if it's low ground by a river |
| **Nearby safer places** | Named shelters and higher ground, with distances |
| **Rescue 1122** | Nearest stations and the district control room number |

Try *Fizagat* (beside the Swat River) to see the danger check say **move away**.

## 3. Risk map

All tehsils, ranked from highest risk. Click one on the map or in the list for its levels, reasons,
exposed villages and river flow. Use **Find a tehsil** to filter.

## 4. Ask Nigehban

Ask in English or Urdu. Each answer that uses data shows **Answer checked** and its sources.

| Try asking | Expect |
|:--|:--|
| *Is there flood risk in Swat tomorrow?* | Babuzai, Swat, very high (replay on) |
| *کیا کل بونیر میں سیلاب کا خطرہ ہے؟* | A full Urdu answer |
| *What should I do if water enters my house?* | Official safety advice |
| *Who won the cricket match?* | A polite "I can only help with floods" |

## 5. Alerts

Alerts are sent when a place reaches **High or Very high** within 2 days.

1. Turn on the **14 Aug 2025** replay.
2. On **Alerts**, add a place that is High that day, such as **Gagra**, **Kabal** or **Mingora**, and
   click **Subscribe to alerts**. The page shows each place's level.
3. Run the alert job:

   ```bash
   python -m pipelines.alerts.run_cycle --as-of 2025-08-14T09:00:00+05:00
   ```

4. Refresh **Alerts**. The alert appears with an Urdu voice note.
5. Run the job again: nothing new arrives, because duplicates are blocked.

**Stop alerts** and **Delete all my data** are on the same page.

## 6. Urdu

Click **اردو** in the header. The whole site switches to Urdu, right to left.

## 7. Authority board

Open http://localhost:3000/board and sign in with `NIGEHBAN_BOARD_PASSWORD`.

- Pick a replay or any date since March 2024.
- Click a tehsil for exposed villages, safer places, Rescue 1122 and river flow.
- **Draft advisory** builds a printable advisory in English and Urdu.

## Shareable links

| Link | Opens |
|:--|:--|
| `/?replay=2025-08-14` | That past day |
| `/area?tehsil=swat__kabal` | My area for one tehsil |
| `/?lang=ur` | The site in Urdu |
