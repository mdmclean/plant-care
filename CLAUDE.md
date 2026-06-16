# Plant Care Daily Routine

## Overview
This repo stores plant care profiles and a care log. The daily routine reads both
to produce a personalized checklist of what each plant needs today.

## Committing & Merging Changes

For **any** requested change (adding a plant, adding a photo, updating the care
log, editing a profile, etc.), do not wait to be asked to ship it. Once the
change is complete, without prompting:

1. Commit with a clear, descriptive message.
2. Push the working branch.
3. Open a PR against `main` via the GitHub MCP, then immediately merge it.

GitHub Actions regenerates the report on merge. Only pause to ask first if a
change is destructive or ambiguous (e.g. deleting a plant, overwriting data).

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

A plant may also have an optional `nickname:` field (a short friendly name,
e.g. `nickname: "Flamingo"` for the anthurium). The list view shows the
nickname when present and falls back to the proper `name` otherwise; the
detail view always shows the proper `name`.

## Adding a Photo of a Plant

Plants keep a **photo history** — each photo is dated, and the report shows a
per-plant gallery that opens on the latest shot and scrolls back through older
ones. The date is overlaid by the report (do NOT burn text into the image).

When the user supplies a photo of a plant, do the following:

1. **Save and downscale the image.** Name it
   `docs/images/<plant-id>-<YYYY-MM-DD>.jpeg` (the plant `id` plus the date the
   photo was taken/added) so each entry in the history is distinct. Photos
   straight from a phone are large (multiple MB / 4000px+), so always downscale
   before committing:
   ```python
   from PIL import Image, ImageOps
   im = Image.open(src)
   im = ImageOps.exif_transpose(im)        # honor camera rotation
   im.thumbnail((1200, 1200), Image.LANCZOS)  # cap longest side at 1200px
   if im.mode != "RGB": im = im.convert("RGB")
   im.save(dest, "JPEG", quality=82, optimize=True)
   ```
   This keeps files around a few hundred KB instead of several MB.
2. **Append it to the plant's `photos` history.** Add a `photos:` list near the
   top of the plant's YAML (just after `name:`), newest entries can go in any
   order — the report sorts by `date`. **Append, never replace** prior photos:
   ```yaml
   photos:
     - file: "images/money-tree-2026-06-15.jpeg"
       date: "2026-06-15"
     - file: "images/money-tree-2026-09-01.jpeg"   # a later check-in
       date: "2026-09-01"
   ```
   (A legacy single `image: "..."` field is still honored as a one-photo,
   undated history.)
3. **Analyze the photo and update the plant's `notes`.** Look at the plant's
   condition and add a dated observation note (e.g.
   `"Photo check (YYYY-MM-DD): ..."`). Call out leaf color, signs of over/under-
   watering (yellowing, browning, drooping, scorch), pests, leggy/stretching
   growth, and anything that suggests a care adjustment. Keep it specific to
   what is actually visible in the image. With a photo history, also compare
   against earlier shots and note visible change (new growth, decline, etc.).
4. **(Optional) Make a background-removed list thumbnail.** The list view shows a
   small avatar per plant from its newest photo. For plants that cut out cleanly
   you can replace that with a background-removed version so the plant floats on
   the card color:
   ```bash
   pip install rembg onnxruntime pillow      # not needed to build the report
   python3 make_thumbnail.py <plant-id>      # writes docs/images/<photo-stem>-thumb.png
   ```
   The report auto-prefers a `<photo-stem>-thumb.png` cutout when it exists and
   otherwise uses the full photo — so this is purely additive. **Only keep a
   cutout when it looks clean.** Solid foliage and clear pots cut out well; fine
   or spiky foliage (palms, ferns, spilling vines) and busy/dark backgrounds
   ghost badly at thumbnail size — for those, delete the generated `-thumb.png`
   and let the plant keep its full-photo avatar. Eyeball the result before
   committing.
5. **Regenerate the report** by running `python3 generate_report.py` (it renders
   the gallery and overlays each photo's date), then commit and push.
