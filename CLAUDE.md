# Plant Care Daily Routine

## Overview
This repo stores plant care profiles and a care log. The daily routine reads both
to produce a personalized checklist of what each plant needs today.

## File Structure

```
plants/              # One YAML file per plant — static care instructions
care_log.yaml        # Tracks the last time each plant was watered / fertilized
generate_report.py   # Generates docs/index.html for GitHub Pages
docs/index.html      # GitHub Pages report (auto-generated — do not edit manually)
CLAUDE.md            # This file — instructions for the daily routine
```

## How to Run the Daily Routine

When invoked, do the following:

1. **Read today's date** and determine the current season/month.
2. **Load all plant files** from the `plants/` directory.
3. **Load `care_log.yaml`** for last-action dates.
4. **For each plant**, evaluate and report:

### Watering check
- Calculate days since `last_watered`.
- Compare against the plant's `watering.estimated_interval_days` for the current
  season (`spring_summer` for months 3–8, `fall_winter` for months 9–2).
- If at or past the estimated interval, flag the plant for a **soil check**.
- Always remind: soil must be checked manually before watering (not a fixed schedule).

### Fertilizing check
- Compare `last_fertilized` against the plant's `feeding.active_months`.
- If the current month is in `active_months` and it has been ≥28 days since
  `last_fertilized`, flag the plant for **fertilizing today**.
- If the current month is NOT in `active_months`, note that feeding is paused.

### General reminders
- Mention the plant's `location` so the user can find it quickly.
- If a plant has `notes`, surface any that are seasonally relevant.

## Output Format

Produce a brief, friendly daily report. Example structure:

```
🌿 Plant Care — [Date]

[Plant Name] — [Location]
  ✅ Watering: Soil check due (last watered X days ago). Check if fully dry before watering.
  ✅ Fertilizer: Due this month — apply half-strength balanced fertilizer.
  💡 Reminder: [relevant note if any]

[Next plant...]
```

If no action is needed for a plant, say so in one line and move on.

## Updating the Log

After the user confirms they've cared for a plant, update `care_log.yaml` with
today's date for the relevant action (`last_watered` and/or `last_fertilized`).

Then, without waiting to be asked, commit the changes, open a PR against `main`,
and immediately merge it. GitHub Actions will automatically regenerate the report.

```bash
git add care_log.yaml plants/*.yaml
git commit -m "care log: update [plant names] — [date]"
git push -u origin <branch>
# create PR via GitHub MCP, then merge it
```

## Adding a New Plant

Create a new file in `plants/` following the same YAML schema as
`plants/hoya-krimson-queen.yaml`. Add a matching entry in `care_log.yaml`.
