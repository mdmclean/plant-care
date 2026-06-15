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

## Adding a Photo of a Plant

When the user supplies a photo of a plant, do the following:

1. **Save and downscale the image.** Store it in `docs/images/<plant-id>.jpeg`
   (matching the plant's `id`). Photos straight from a phone are large
   (multiple MB / 4000px+), so always downscale before committing:
   ```python
   from PIL import Image, ImageOps
   im = Image.open(src)
   im = ImageOps.exif_transpose(im)        # honor camera rotation
   im.thumbnail((1200, 1200), Image.LANCZOS)  # cap longest side at 1200px
   if im.mode != "RGB": im = im.convert("RGB")
   im.save(dest, "JPEG", quality=82, optimize=True)
   ```
   This keeps files around a few hundred KB instead of several MB.
   Then **stamp the date added** in the bottom-right corner so each photo
   carries its own timeline:
   ```python
   from PIL import ImageDraw, ImageFont
   text = f"Added {today}"            # today as YYYY-MM-DD
   size = max(16, im.width // 28)
   try:    font = ImageFont.truetype("DejaVuSans-Bold.ttf", size)
   except Exception: font = ImageFont.load_default(size)
   draw = ImageDraw.Draw(im)
   l, t, r, b = draw.textbbox((0, 0), text, font=font)
   pad = max(8, im.width // 100)
   x, y = im.width - (r - l) - pad * 2, im.height - (b - t) - pad * 2
   ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
   ImageDraw.Draw(ov).rectangle([x - pad, y - pad, x + (r - l) + pad, y + (b - t) + pad], fill=(0, 0, 0, 140))
   im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
   ImageDraw.Draw(im).text((x - l, y - t), text, font=font, fill=(255, 255, 255))
   ```
   Stamp the photo *before* saving the final JPEG.
2. **Link it from the plant file.** Add an `image: "images/<plant-id>.jpeg"`
   field near the top of the plant's YAML (just after `name:`), matching the
   pattern in `plants/hoya-krimson-queen.yaml`.
3. **Analyze the photo and update the plant's `notes`.** Look at the plant's
   condition and add a dated observation note (e.g.
   `"Photo check (YYYY-MM-DD): ..."`). Call out leaf color, signs of over/under-
   watering (yellowing, browning, drooping, scorch), pests, leggy/stretching
   growth, and anything that suggests a care adjustment. Keep it specific to
   what is actually visible in the image.
4. **Regenerate the report** by running `python3 generate_report.py` (the report
   displays the photo), then commit and push.
