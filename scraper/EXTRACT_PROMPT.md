# GDiDM Events Extraction — Claude Code Prompt

Use this prompt to guide the extraction step after running `python scraper/scrape.py`.

---

## Instructions

Read all `.txt` files in `scraper/pages/`. For each file, extract any events or opportunities related to the **digital minds** field. Output a JSON array to `scraper/scraped_events.json`.

Each event should be a JSON object with these fields:

```json
{
  "title": "string (required) — event name",
  "url": "string (required) — link to event page",
  "organiser": "string (required) — organisation running the event",
  "start_date": "YYYY-MM-DD (required) — event start date",
  "end_date": "YYYY-MM-DD or null — event end date if multi-day",
  "type": "conference | workshop | fellowship | course | seminar | programme",
  "format": "in-person | online | hybrid",
  "location": "string — city/country or 'Online'",
  "deadline": "YYYY-MM-DD or null — application/registration deadline",
  "description": "string — 1-2 sentence description",
  "confidence": "high | medium | low"
}
```

## Event type definitions

| Type | Definition |
|---|---|
| **conference** | Multi-day gathering with talks, panels, posters. Usually annual. |
| **workshop** | Shorter, more focused. Often attached to a conference or standalone 1-2 day event. |
| **fellowship** | Funded position (weeks to months) involving research or professional development. |
| **course** | Structured learning programme with curriculum, often with application process. |
| **programme** | Broader category — mentorship, research sprints, cohort-based activities. |
| **seminar** | Single talk or panel, often part of a recurring series. |

## What counts as a "digital minds" event

### Core terms (high relevance — always include)

- Digital minds
- AI consciousness / machine consciousness
- AI sentience / artificial sentience
- AI welfare
- AI moral status / moral patienthood
- Phenomenal consciousness (applied to AI)
- AI moral consideration

### Theory terms (high relevance in context)

- Integrated Information Theory (IIT)
- Global Workspace Theory (GWT)
- Higher-Order Theories (HOT)
- Recurrence Processing Theory (RPT)
- Attention Schema Theory (AST)
- Indicator properties (consciousness)

### Policy and governance terms (medium relevance)

- Precautionary principle applied to AI consciousness
- Capability welfare gap
- Digital minds policy
- AI rights
- Moral uncertainty (re: AI)

### Adjacent terms (include if combined with core terms)

- Mechanistic interpretability (when linked to consciousness)
- AI alignment (when discussing value alignment with potentially conscious AI)
- AI safety (when intersecting with welfare/consciousness)
- Animal sentience / animal welfare (when comparative — extending to AI)
- Philosophy of mind (when applied to AI specifically)

### Exclude unless clearly connected

- General AI ethics (fairness, bias, privacy) without consciousness/sentience angle
- Pure technical ML/AI without consciousness connection
- Neuroscience events without AI application
- General philosophy conferences without AI/digital minds sessions

## Confidence levels

- **high**: Event is clearly about digital minds topics, dates are explicit, all required fields found
- **medium**: Event is relevant but some fields are inferred or uncertain (e.g. date estimated from context, format unclear)
- **low**: Event may be relevant but connection to digital minds is indirect, or key details are missing

## Output rules

1. Only include events that have not clearly passed (use today's date as reference)
2. If a page has no relevant events, skip it — do not fabricate entries
3. If dates are vague (e.g. "Spring 2026"), set `start_date` to null and note in description
4. The `url` should be the most specific event page URL, not the org homepage (use the URL from the file header if the page itself is the event page)
5. Write the output to `scraper/scraped_events.json` as a JSON array

## Example output

```json
[
  {
    "title": "Cambridge Digital Minds Fellowship 2026",
    "url": "https://digitalminds.cam/fellowship/",
    "organiser": "Cambridge Digital Minds",
    "start_date": "2026-07-14",
    "end_date": "2026-07-20",
    "type": "fellowship",
    "format": "in-person",
    "location": "Cambridge, UK",
    "deadline": "2026-03-27",
    "description": "Five-day residential programme at Jesus College followed by the Digital Minds Strategy Workshop. Fully funded.",
    "confidence": "high"
  }
]
```
