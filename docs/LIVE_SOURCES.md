# Bonus: live source — events next to the business

**Replaced:** `data/local_events.json` (synthetic) → **Helsinki LinkedEvents API** (`api.hel.fi/linkedevents/v1`, CC BY 4.0), live, queried on 7 Nov 2026.
**Used for:** "Stay open later?" suggestions for restaurants, bars and pizzerias when an evening event within 1 km ends after closing time. Proposed close = event end + 1 h, at most 2 h later than now, always as a question (confidence 0.5). The owner decides.

Code: `app/events.py`, `Engine.event_suggestions`. Curated fallback for cities with no open events API: `app/data/curated_events.json`.

## What we learned (measured 7 Nov 2026, Helsinki region, 7–9 Nov evenings)

- **Coverage:** 235 events started after 12:00 and lasted at most 8 h in the 3 evenings, all with coordinates. Helsinki region only. Turku's LinkedEvents endpoints (`api.turku.fi/linkedevents`, `linkedevents-api.turku.fi`) did not answer, so the rest of Finland, Sweden and Norway needs other sources (Kuopio, Oslo, Stockholm city calendars, ticketing APIs).
- **Quality:** 14 of 235 had no end time or end = start (theatre shows). We assume 2.5 h. There's no attendance figure at all, so "big event" can't be judged from this API alone. That's the biggest gap: a sold-out 3,000-seat concert and a 20-seat workshop look the same.
- **Gotcha:** a plain `start`/`end` query returns season-long exhibitions first (started in 2001…2019). You need `max_duration=8h` plus an afternoon `start` to get the evening programme.
- **Signal value:** across 106 Helsinki restaurants, bars and pizzerias, only 5 got a suggestion for this weekend. All 5 are pizzerias near Temppeliaukio church, where a concert ends 20:15 and they close 20:00. It's a useful but rare signal. Without attendance data it should stay a question, never an automatic change.
- **In production:** LinkedEvents (Helsinki, Espoo), Ticketmaster/Lippupiste/Tiketti venue feeds for attendance, the arenas' own calendars, plus each city's open data where it exists.
