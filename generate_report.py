#!/usr/bin/env python3
"""Generate a GitHub Pages HTML report from plant care data."""

import re
import yaml
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).parent
PLANTS_DIR = BASE / "plants"
CARE_LOG = BASE / "care_log.yaml"
OUTPUT = BASE / "docs" / "index.html"

SPRING_SUMMER = set(range(3, 9))  # March–August


def load_plants():
    plants = {}
    for f in sorted(PLANTS_DIR.glob("*.yaml")):
        with open(f) as fh:
            plants[f.stem] = yaml.safe_load(fh)
    return plants


def find_plant(log_key, plants):
    if log_key in plants:
        return plants[log_key]
    # Snake-plant-1 / snake-plant-2 → snake-plant
    base = re.sub(r"-\d+$", "", log_key)
    return plants.get(base)


def days_since(val):
    if not val:
        return None
    return (date.today() - datetime.strptime(str(val), "%Y-%m-%d").date()).days


def evaluate(log_key, log_entry, plant):
    today = date.today()
    month = today.month
    season = "spring_summer" if month in SPRING_SUMMER else "fall_winter"

    name = plant.get("name", log_key)
    suffix = re.search(r"-(\d+)$", log_key)
    if suffix:
        name = f"{name} #{suffix.group(1)}"

    location = plant.get("location") or ""

    # Watering
    days_w = days_since((log_entry or {}).get("last_watered"))
    interval = ((plant.get("watering") or {}).get("estimated_interval_days") or {}).get(season, 14)
    if days_w is None:
        water = ("unknown", "No watering record")
    elif days_w >= interval:
        water = ("check", f"Soil check due — last watered {days_w}d ago (interval: {interval}d). Check if fully dry before watering.")
    else:
        water = ("ok", f"Last watered {days_w}d ago — next check in ~{interval - days_w}d")

    # Fertilizer
    active = (plant.get("feeding") or {}).get("active_months") or []
    days_f = days_since((log_entry or {}).get("last_fertilized"))
    if month in active:
        if days_f is None or days_f >= 28:
            last_str = f"{days_f}d ago" if days_f else "never recorded"
            fert = ("due", f"Due this month — apply half-strength fertilizer (last: {last_str})")
        else:
            fert = ("ok", f"Last fertilized {days_f}d ago — next due in ~{28 - days_f}d")
    else:
        fert = ("paused", f"Feeding paused — not in active season")

    notes = plant.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]

    return dict(name=name, location=location,
                water_status=water[0], water_msg=water[1],
                fert_status=fert[0], fert_msg=fert[1],
                notes=notes)


BADGE_STYLES = {
    "ok":      ("#e8f5e9", "#2e7d32", "#4caf50"),
    "check":   ("#fff3e0", "#bf360c", "#ff9800"),
    "due":     ("#e3f2fd", "#1565c0", "#2196f3"),
    "paused":  ("#f5f5f5", "#757575", "#bdbdbd"),
    "unknown": ("#fce4ec", "#880e4f", "#e91e63"),
}


def badge(status, icon, msg):
    bg, fg, border = BADGE_STYLES.get(status, BADGE_STYLES["unknown"])
    return (f'<div class="badge" style="background:{bg};color:{fg};'
            f'border-left:4px solid {border}">{icon} {msg}</div>')


def card(r):
    has_action = r["water_status"] == "check" or r["fert_status"] == "due"
    if r["water_status"] == "check":
        top_border = "#ff9800"
    elif r["fert_status"] == "due":
        top_border = "#2196f3"
    else:
        top_border = "#c8e6c9"

    loc = f'<div class="location">📍 {r["location"]}</div>' if r["location"] else ""

    notes_html = ""
    if r["notes"]:
        items = "".join(f"<li>{n}</li>" for n in r["notes"])
        notes_html = f'<div class="notes"><strong>💡</strong><ul>{items}</ul></div>'

    return f"""<div class="card" style="border-top:4px solid {top_border}">
  <div class="card-header">
    <div class="plant-name">{r['name']}</div>
    {loc}
  </div>
  {badge(r['water_status'], '💧', r['water_msg'])}
  {badge(r['fert_status'], '🌱', r['fert_msg'])}
  {notes_html}
</div>"""


def render(results, today):
    action = [r for r in results if r["water_status"] == "check" or r["fert_status"] == "due"]
    good = [r for r in results if r not in action]

    def section(title, items):
        if not items:
            return ""
        cards = "\n".join(card(r) for r in items)
        return f'<h2 class="section-title">{title}</h2><div class="grid">{cards}</div>'

    action_sec = section(f"⚠️ Action Needed ({len(action)})", action)
    good_sec = section(f"✅ All Good ({len(good)})", good)

    day = today.strftime("%-d")
    full_date = today.strftime(f"%A, %B {day}, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>🌿 Plant Care — {today.strftime(f'%B {day}, %Y')}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f8e9;color:#1b1b1b;min-height:100vh}}
    header{{background:linear-gradient(135deg,#2e7d32,#66bb6a);color:#fff;padding:2rem;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.15)}}
    header h1{{font-size:2rem;font-weight:700;letter-spacing:-.5px}}
    header .date{{opacity:.9;margin-top:.4rem;font-size:1.05rem}}
    main{{max-width:1100px;margin:0 auto;padding:2rem 1rem 3rem}}
    .section-title{{font-size:1.05rem;font-weight:700;margin:2rem 0 1rem;padding:.5rem 1rem;border-radius:8px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem}}
    .card{{background:#fff;border-radius:12px;padding:1.25rem;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
    .card-header{{margin-bottom:.75rem}}
    .plant-name{{font-size:1.05rem;font-weight:700;color:#1b5e20}}
    .location{{font-size:.82rem;color:#666;margin-top:.2rem}}
    .badge{{padding:.5rem .75rem;border-radius:6px;margin:.3rem 0;font-size:.85rem;line-height:1.45}}
    .notes{{margin-top:.75rem;padding:.65rem .75rem;background:#fffde7;border-radius:6px;font-size:.78rem;border-left:3px solid #f9a825}}
    .notes ul{{margin-left:1.1rem;margin-top:.3rem}}
    .notes li{{margin:.2rem 0;color:#555;line-height:1.4}}
    footer{{text-align:center;padding:1.5rem;color:#888;font-size:.78rem;border-top:1px solid #dcedc8}}
  </style>
</head>
<body>
  <header>
    <h1>🌿 Plant Care</h1>
    <div class="date">{full_date}</div>
  </header>
  <main>
    {action_sec}
    {good_sec}
  </main>
  <footer>Updated by daily routine · {today.isoformat()}</footer>
</body>
</html>"""


def main():
    plants = load_plants()
    care_log = yaml.safe_load(CARE_LOG.read_text()) or {}
    today = date.today()

    results = []
    for log_key, log_entry in care_log.items():
        plant = find_plant(log_key, plants)
        if plant is None:
            print(f"Warning: no plant file for '{log_key}' — skipping")
            continue
        results.append(evaluate(log_key, log_entry, plant))

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(render(results, today))
    print(f"Report written → {OUTPUT}")


if __name__ == "__main__":
    main()
