#!/usr/bin/env python3
"""Generate a GitHub Pages HTML report from plant care data."""

import json
import math
import re
import struct
import zlib
import yaml
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).parent
PLANTS_DIR = BASE / "plants"
CARE_LOG = BASE / "care_log.yaml"
OUTPUT = BASE / "docs" / "index.html"

SPRING_SUMMER = set(range(3, 9))  # March–August

# ── Lucide icons (inline SVG) ──────────────────────────────────────────────
# Inner markup for each Lucide icon we use (Lucide v1.21.0, ISC licensed). The
# icons are inlined rather than loaded from a CDN so the PWA stays fully offline
# (the service worker only caches local assets). The same map is also injected
# into the page's JS so client-rendered markup can build icons too.
ICON_PATHS = {
    "leaf": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
    "droplet": '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
    "droplets": '<path d="M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z"/><path d="M12.56 6.6A10.97 10.97 0 0 0 14 3.02c.5 2.5 2 4.9 4 6.5s3 3.5 3 5.5a6.98 6.98 0 0 1-11.91 4.97"/>',
    "sprout": '<path d="M14 9.536V7a4 4 0 0 1 4-4h1.5a.5.5 0 0 1 .5.5V5a4 4 0 0 1-4 4 4 4 0 0 0-4 4c0 2 1 3 1 5a5 5 0 0 1-1 3"/><path d="M4 9a5 5 0 0 1 8 4 5 5 0 0 1-8-4"/><path d="M5 21h14"/>',
    "map-pin": '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    "triangle-alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "circle-check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "lightbulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "maximize": '<path d="M15 3h6v6"/><path d="m21 3-7 7"/><path d="m3 21 7-7"/><path d="M9 21H3v-6"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-up": '<path d="m18 15-6-6-6 6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "clipboard": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    "menu": '<line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="18" y2="18"/>',
    "images": '<path d="M18 22H4a2 2 0 0 1-2-2V6"/><path d="m22 13-1.296-1.296a2.41 2.41 0 0 0-3.408 0L11 18"/><circle cx="12" cy="8" r="2"/><rect width="16" height="16" x="6" y="2" rx="2"/>',
    "list-checks": '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
}


def icon(name, cls=""):
    """Render an inline Lucide SVG icon. `cls` adds extra classes alongside `ic`."""
    classes = ("ic " + cls).strip()
    return (
        f'<svg class="{classes}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{ICON_PATHS[name]}</svg>'
    )

MANIFEST = {
    "name": "Plant Care",
    "short_name": "Plants",
    "start_url": ".",
    "display": "standalone",
    "background_color": "#eef1ef",
    "theme_color": "#064e3b",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    ],
}


def _sw_js(today_str: str) -> str:
    return f"""const CACHE = 'plant-care-{today_str}';
const ASSETS = ['./index.html', './manifest.json', './icon-192.png', './icon-512.png'];

self.addEventListener('install', e => {{
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
}});

self.addEventListener('activate', e => {{
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
}});

self.addEventListener('fetch', e => {{
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
}});
"""


def _make_icon_png(size: int) -> bytes:
    """Generate a simple plant-care PNG icon: dark green background, white leaf + stem."""
    bg = (46, 125, 50)   # #2e7d32
    fg = (255, 255, 255)

    cx = cy = size / 2
    a, b = size * 0.30, size * 0.16   # leaf ellipse semi-axes
    stem_hw = max(1, size // 60)
    stem_top = cy - size * 0.05
    stem_bot = cy + size * 0.32
    cos45 = sin45 = math.sqrt(2) / 2

    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter byte
        for x in range(size):
            dx, dy = x - cx, y - cy
            rx =  dx * cos45 + dy * sin45
            ry = -dx * sin45 + dy * cos45
            in_leaf = (rx / a) ** 2 + (ry / b) ** 2 <= 1
            in_stem = abs(dx) <= stem_hw and stem_top <= y <= stem_bot
            raw += bytes(fg if (in_leaf or in_stem) else bg)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">II", size, size) + bytes([8, 2, 0, 0, 0])
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


def load_plants():
    plants = {}
    for f in sorted(PLANTS_DIR.glob("*.yaml")):
        with open(f) as fh:
            plants[f.stem] = yaml.safe_load(fh)
    return plants


def find_plant(log_key, plants):
    if log_key in plants:
        return plants[log_key]
    base = re.sub(r"-\d+$", "", log_key)
    return plants.get(base)


def days_since(val):
    if not val:
        return None
    return (date.today() - datetime.strptime(str(val), "%Y-%m-%d").date()).days


def _fmt_photo_date(s):
    """Format an ISO date string for the photo overlay, e.g. 'Jun 15, 2026'."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime(f"%b {datetime.strptime(s, '%Y-%m-%d').day}, %Y")
    except Exception:
        return s


def photo_list(plant):
    """Return a plant's photos as a chronological list (oldest → newest).

    Accepts either a `photos:` list (each item a dict with `file` + `date`, or a
    bare path string) or a legacy single `image:` field. Each returned item has
    `src`, `date`, and a display `label`.
    """
    raw = plant.get("photos")
    items = []
    if raw:
        for ph in raw:
            if isinstance(ph, str):
                items.append({"src": ph, "date": ""})
            elif isinstance(ph, dict) and ph.get("file"):
                items.append({"src": ph["file"], "date": str(ph.get("date") or "")})
    else:
        img = plant.get("image")
        if img:
            items.append({"src": img, "date": ""})
    # Oldest first; undated entries sort ahead of dated ones (empty string < any date).
    items.sort(key=lambda p: p["date"])
    for it in items:
        it["label"] = _fmt_photo_date(it["date"]) if it["date"] else ""
    return items


def thumb_for(photos):
    """Return a background-removed cutout thumbnail for the newest photo, if one
    has been generated (see make_thumbnail.py). The cutout sits at
    `<photo-stem>-thumb.png` next to the photo; when present the list-view avatar
    uses it (plant floating on the card color) instead of the full photo."""
    if not photos:
        return None
    src = photos[-1]["src"]  # newest (photos are oldest→newest)
    cand = src.rsplit(".", 1)[0] + "-thumb.png"
    return cand if (OUTPUT.parent / cand).exists() else None


def evaluate(log_key, log_entry, plant):
    today = date.today()
    month = today.month
    season = "spring_summer" if month in SPRING_SUMMER else "fall_winter"

    name = plant.get("name", log_key)
    # Optional friendly nickname used in the list view (falls back to `name`).
    nickname = plant.get("nickname") or ""
    suffix = re.search(r"-(\d+)$", log_key)
    if suffix:
        name = f"{name} #{suffix.group(1)}"
        if nickname:
            nickname = f"{nickname} #{suffix.group(1)}"

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

    # Fertilizer — liquid feed is delivered with a watering, so only call it
    # "due" today if we're also watering today. Otherwise it waits for the next
    # watering (informational, not an attention item).
    watering_occasion = water[0] != "ok"
    active = (plant.get("feeding") or {}).get("active_months") or []
    days_f = days_since((log_entry or {}).get("last_fertilized"))
    if month in active:
        if days_f is None or days_f >= 28:
            last_str = f"{days_f}d ago" if days_f else "never recorded"
            if watering_occasion:
                fert = ("due", f"Due now — feed with today's watering (half-strength; last: {last_str})")
            else:
                fert = ("pending", f"Feed with next watering — overdue but soil isn't dry yet (last: {last_str})")
        else:
            fert = ("ok", f"Last fertilized {days_f}d ago — next due in ~{28 - days_f}d")
    else:
        fert = ("paused", "Feeding paused — not in active season")

    notes = plant.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]

    photos = photo_list(plant)
    return dict(
        id=log_key,
        name=name,
        nickname=nickname,
        location=location,
        photos=photos,
        thumb=thumb_for(photos),
        water_status=water[0],
        water_msg=water[1],
        fert_status=fert[0],
        fert_msg=fert[1],
        notes=notes,
        has_action=(water[0] == "check" or fert[0] == "due"),
    )


def render(results, today):
    action = [r for r in results if r["has_action"]]
    good = [r for r in results if not r["has_action"]]
    ordered = action + good

    plants_json = json.dumps([{
        "id": r["id"],
        "name": r["name"],
        "nickname": r["nickname"],
        "location": r["location"],
        "photos": r["photos"],
        "thumb": r["thumb"],
        "waterStatus": r["water_status"],
        "waterMsg": r["water_msg"],
        "fertStatus": r["fert_status"],
        "fertMsg": r["fert_msg"],
        "notes": r["notes"],
        "hasAction": r["has_action"],
    } for r in ordered])

    icons_json = json.dumps(ICON_PATHS)

    day = today.strftime("%-d")
    short_date = today.strftime(f"%b {day}")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>Plant Care</title>
  <link rel="manifest" href="manifest.json">
  <meta name="theme-color" content="#064e3b" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#053a2b" media="(prefers-color-scheme: dark)">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Plant Care">
  <link rel="apple-touch-icon" href="icon-192.png">
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #eef1ef; --surface: #ffffff; --surface-2: #f3f5f4;
      --border: #e4e8e6;
      --shadow: 0 1px 2px rgba(16,24,20,.05), 0 6px 16px rgba(16,24,20,.06);
      --shadow-up: 0 -1px 16px rgba(16,24,20,.07);
      --text: #111714; --text-2: #5d6a64; --text-3: #aeb6b1;
      --accent: #059669; --accent-press: #047857; --on-accent: #ffffff;
      --accent-shadow: 0 6px 18px rgba(5,150,105,.32);
      --header-bg: linear-gradient(135deg, #064e3b 0%, #0a7d59 100%);
      --warn: #f59e0b; --warn-bg: #fff3df; --warn-text: #8a3a05;
      --info: #3b82f6; --info-bg: #e7eeff; --info-text: #1d4ed8;
      --ok: #10b981; --ok-bg: #e1f6ee; --ok-text: #047857;
      --ok-solid: #059669; --info-solid: #2563eb;
      --paused: #9aa7a1; --paused-bg: #eef1ef; --paused-text: #6b766f;
      --danger: #ef4444; --danger-bg: #fce8ea; --danger-text: #be123c;
      --note-bg: #fff8e6; --note-border: #f59e0b; --note-text: #7a5e16;
      --toast-bg: #16201c; --toast-text: #f2f5f3;
      --radius: 16px; --radius-sm: 12px; --radius-pill: 999px;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0c100e; --surface: #161d19; --surface-2: #1e2622;
        --border: rgba(255,255,255,.09);
        --shadow: 0 1px 2px rgba(0,0,0,.5), 0 8px 20px rgba(0,0,0,.4);
        --shadow-up: 0 -2px 18px rgba(0,0,0,.45);
        --text: #e9efec; --text-2: #93a29b; --text-3: #5e6a64;
        --accent: #10b981; --accent-press: #0c9a6c; --on-accent: #04130d;
        --accent-shadow: 0 6px 20px rgba(16,185,129,.28);
        --header-bg: linear-gradient(135deg, #053a2b 0%, #066a4b 100%);
        --warn: #fbbf24; --warn-bg: rgba(251,191,36,.14); --warn-text: #fcd34d;
        --info: #60a5fa; --info-bg: rgba(96,165,250,.15); --info-text: #93c5fd;
        --ok: #34d399; --ok-bg: rgba(52,211,153,.15); --ok-text: #6ee7b7;
        --ok-solid: #047857; --info-solid: #1d4ed8;
        --paused: #6b766f; --paused-bg: rgba(255,255,255,.05); --paused-text: #9aa7a1;
        --danger: #f87171; --danger-bg: rgba(248,113,113,.15); --danger-text: #fca5a5;
        --note-bg: rgba(251,191,36,.1); --note-border: #fbbf24; --note-text: #e6d6a8;
        --toast-bg: #eef1ef; --toast-text: #15201c;
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }}
    .hidden {{ display: none !important; }}

    /* ── Inline Lucide icons ── */
    /* Icons scale with the surrounding font-size (1em) and inherit text color
       via currentColor, so they slot in wherever an emoji used to sit. */
    .ic {{ width: 1em; height: 1em; display: inline-block; vertical-align: -.14em;
           stroke: currentColor; fill: none; flex: none; }}
    .hdr-title .ic {{ vertical-align: -.16em; margin-right: .15rem; }}
    .sec-label {{ display: flex; align-items: center; gap: .35rem; }}
    .sec-label .ic {{ width: 1.05em; height: 1.05em; }}
    .row-avatar > .ic {{ width: 22px; height: 22px; color: var(--text-3); }}
    .need-chip .ic {{ width: .95em; height: .95em; }}
    .chevron {{ display: flex; align-items: center; }}
    .chk .ic, .d-chk .ic {{ width: 1.25em; height: 1.25em; }}
    .back-btn {{ display: inline-flex; align-items: center; gap: .3rem; }}
    .nav-btn {{ display: inline-flex; align-items: center; justify-content: center; }}
    .nav-btn .ic {{ width: 1.2em; height: 1.2em; }}
    .copy-btn, .d-chk {{ display: inline-flex; align-items: center; justify-content: center; gap: .4rem; }}
    .badge .ic, .d-loc .ic, .row-loc .ic, .bar-count .ic {{ vertical-align: -.15em; }}
    html, body {{ height: 100%; overflow: hidden; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif;
            background: var(--bg); color: var(--text);
            -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }}

    /* ── Views ── */
    .view {{ position: fixed; inset: 0; display: flex; flex-direction: column; }}

    /* ── Header ── */
    .hdr {{ background: var(--header-bg); color: #fff;
            display: flex; align-items: center; gap: .65rem;
            padding: calc(.95rem + env(safe-area-inset-top)) 1.1rem .95rem;
            flex-shrink: 0; position: relative; z-index: 2; }}
    .hdr-title {{ flex: 1; font-size: 1.15rem; font-weight: 800; min-width: 0;
                  letter-spacing: -.02em;
                  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .hdr-sub {{ font-size: .68rem; font-weight: 700; letter-spacing: .06em;
                text-transform: uppercase; white-space: nowrap;
                background: rgba(255,255,255,.18); color: #fff;
                padding: .3rem .6rem; border-radius: var(--radius-pill); }}
    .back-btn {{ background: rgba(255,255,255,.16); border: none; color: #fff;
                 border-radius: 10px; padding: .42rem .8rem; font-size: .85rem;
                 font-weight: 600; cursor: pointer; flex-shrink: 0; }}
    .back-btn:active {{ background: rgba(255,255,255,.32); }}
    .icon-btn {{ padding: .42rem .58rem; line-height: 1; }}

    /* ── List ── */
    #list-scroll {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
                    padding-bottom: .4rem; }}
    .sec-label {{ font-size: .7rem; font-weight: 800; letter-spacing: .09em;
                  text-transform: uppercase; color: var(--text-2);
                  padding: 1.1rem 1.15rem .4rem; }}
    .sec-label.warn {{ color: var(--warn-text); }}
    .row {{ position: relative; display: flex; align-items: center; gap: .6rem;
            background: var(--surface); border: 1px solid var(--border);
            margin: .45rem .8rem; border-radius: var(--radius);
            padding: .9rem .8rem; cursor: pointer; box-shadow: var(--shadow);
            transition: transform .12s ease, background .12s ease; }}
    .row:active {{ transform: scale(.988); background: var(--surface-2); }}
    .row.urgent::before {{ content: ''; position: absolute; left: 0; top: 13px; bottom: 13px;
                           width: 4px; border-radius: 0 4px 4px 0; background: var(--warn); }}
    /* Small uniform thumbnail docked at the far left. A leaf icon sits behind
       as the placeholder; the photo covers it when loaded and removes itself on
       error, falling back to the leaf. Sized to keep the row compact. */
    .row-avatar {{ position: relative; width: 40px; height: 40px; flex-shrink: 0;
                   border-radius: 11px; overflow: hidden; display: flex;
                   align-items: center; justify-content: center; font-size: 1.2rem;
                   background: var(--surface-2); border: 1px solid var(--border); }}
    .row-avatar img {{ position: absolute; inset: 0; width: 100%; height: 100%;
                       object-fit: cover; }}
    /* Cutout thumbnails are transparent: let the card color show through and
       give the plant a little breathing room rather than cropping to the edge. */
    .row-avatar.cut img {{ inset: 3px; width: calc(100% - 6px); height: calc(100% - 6px);
                           object-fit: contain; }}
    .row-info {{ flex: 1; min-width: 0; }}
    .row-name {{ font-weight: 700; font-size: .96rem; letter-spacing: -.01em;
                 white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .row-loc {{ font-size: .76rem; color: var(--text-2); margin-top: .2rem;
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .row-needs {{ display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .4rem; }}
    .need-chip {{ font-size: .7rem; font-weight: 700; letter-spacing: -.01em;
                  padding: .16rem .5rem; border-radius: var(--radius-sm);
                  display: inline-flex; align-items: center; gap: .25rem;
                  border: 1px solid transparent; max-width: 100%; }}
    .need-chip.water,
    .need-chip.fert    {{ background: var(--warn-bg);   color: var(--warn-text);   border-color: var(--warn); }}
    .need-chip.unknown {{ background: var(--danger-bg); color: var(--danger-text); border-color: var(--danger); }}
    .need-chip.soon    {{ background: var(--paused-bg); color: var(--paused-text); border-color: var(--border); }}
    .row-dots {{ display: flex; gap: .25rem; flex-shrink: 0; }}
    .chevron {{ color: var(--text-3); font-size: 1.05rem; flex-shrink: 0; margin-left: 0; }}

    /* ── Detail ── */
    #detail-scroll {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
                      padding: 1.1rem .9rem 6rem; }}
    .d-name {{ font-size: 1.2rem; font-weight: 800; color: var(--text);
               margin-bottom: .3rem; letter-spacing: -.02em; line-height: 1.2; }}
    .d-loc {{ font-size: .82rem; color: var(--text-2); margin-bottom: 1rem; }}
    .badge {{ padding: .5rem .75rem; border-radius: var(--radius-sm); margin: .35rem 0;
              font-size: .85rem; line-height: 1.4; font-weight: 500; border-left: 3px solid; }}
    .badge.check   {{ background: var(--warn-bg);   color: var(--warn-text);   border-color: var(--warn); }}
    .badge.due     {{ background: var(--info-bg);   color: var(--info-text);   border-color: var(--info); }}
    .badge.pending {{ background: var(--paused-bg); color: var(--paused-text); border-color: var(--paused); }}
    .badge.ok      {{ background: var(--ok-bg);     color: var(--ok-text);     border-color: var(--ok); }}
    .badge.paused  {{ background: var(--paused-bg); color: var(--paused-text); border-color: var(--paused); }}
    .badge.unknown {{ background: var(--danger-bg); color: var(--danger-text); border-color: var(--danger); }}
    .notes {{ margin-top: 1rem; padding: .85rem .9rem; background: var(--note-bg);
              border-radius: var(--radius-sm); border-left: 3px solid var(--note-border);
              font-size: .82rem; color: var(--note-text); }}
    .notes strong {{ color: var(--text); }}
    .notes ul {{ margin-left: 1.1rem; margin-top: .5rem; }}
    .notes li {{ margin: .55rem 0; line-height: 1.6; }}

    /* ── Detail nav bar ── */
    .d-nav {{ position: fixed; bottom: 0; left: 0; right: 0; display: flex;
              align-items: center; gap: .75rem; background: var(--surface);
              border-top: 1px solid var(--border);
              padding: .7rem 1rem calc(.7rem + env(safe-area-inset-bottom));
              box-shadow: var(--shadow-up); }}
    .nav-btn {{ background: var(--surface-2); border: 1px solid var(--border);
                color: var(--text); border-radius: var(--radius-sm);
                padding: .55rem 1.1rem; font-size: 1rem; font-weight: 700;
                cursor: pointer; flex-shrink: 0; }}
    .nav-btn:active {{ background: var(--bg); }}
    .nav-btn:disabled {{ opacity: .3; pointer-events: none; }}
    .nav-hint {{ flex: 1; font-size: .73rem; color: var(--text-2); text-align: center;
                 overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

    /* ── Plant photo gallery ── */
    .gallery {{ position: relative; margin-bottom: 1rem; }}
    .gallery-track {{ display: flex; overflow-x: auto; scroll-snap-type: x mandatory;
                      -webkit-overflow-scrolling: touch; border-radius: var(--radius);
                      border: 1px solid var(--border); background: var(--surface-2);
                      scrollbar-width: none; }}
    .gallery-track::-webkit-scrollbar {{ display: none; }}
    .slide {{ position: relative; flex: 0 0 100%; scroll-snap-align: center; }}
    .plant-photo {{ width: 100%; height: 260px; object-fit: cover; display: block;
                    background: var(--surface-2); }}
    .photo-date {{ position: absolute; right: .55rem; bottom: .55rem;
                   background: rgba(0,0,0,.58); color: #fff; font-size: .72rem; font-weight: 700;
                   padding: .26rem .58rem; border-radius: var(--radius-pill);
                   letter-spacing: .02em; }}
    .g-nav {{ position: absolute; top: 50%; transform: translateY(-50%);
              width: 34px; height: 34px; border-radius: 50%; border: none;
              background: rgba(0,0,0,.42); color: #fff; font-size: 1.4rem; line-height: 1;
              cursor: pointer; display: flex; align-items: center; justify-content: center;
              padding-bottom: 3px; }}
    .g-prev {{ left: .5rem; }}
    .g-next {{ right: .5rem; }}
    .g-nav:active {{ background: rgba(0,0,0,.72); }}
    .g-nav:disabled {{ opacity: 0; pointer-events: none; }}
    .g-dots {{ position: absolute; left: 0; right: 0; bottom: .5rem; display: flex;
               justify-content: center; gap: .32rem; }}
    .g-dot {{ width: 6px; height: 6px; border-radius: 50%; background: rgba(255,255,255,.55);
              cursor: pointer; transition: background .15s, width .15s, height .15s; }}
    .g-dot.active {{ background: #fff; width: 7px; height: 7px; }}
    /* A small "maximize" affordance on each slide; the photo itself is also
       tappable. Both open the full-screen zoomable viewer. */
    .plant-photo {{ cursor: zoom-in; }}
    .g-zoom {{ position: absolute; top: .5rem; right: .5rem; width: 32px; height: 32px;
               border-radius: 50%; border: none; background: rgba(0,0,0,.42); color: #fff;
               font-size: 1rem; line-height: 1; cursor: pointer; display: flex;
               align-items: center; justify-content: center; }}
    .g-zoom:active {{ background: rgba(0,0,0,.72); }}

    /* ── Header sub menu ── */
    .menu-wrap {{ position: relative; flex-shrink: 0; }}
    .menu-pop {{ position: absolute; top: calc(100% + .45rem); right: 0; z-index: 30;
                 min-width: 200px; background: var(--surface); color: var(--text);
                 border: 1px solid var(--border); border-radius: var(--radius-sm);
                 box-shadow: var(--shadow); overflow: hidden; }}
    .menu-item {{ display: flex; align-items: center; gap: .6rem; width: 100%;
                  padding: .8rem .95rem; background: none; border: none;
                  color: var(--text); font-size: .9rem; font-weight: 600;
                  cursor: pointer; text-align: left; }}
    .menu-item + .menu-item {{ border-top: 1px solid var(--border); }}
    .menu-item:active {{ background: var(--surface-2); }}
    .menu-item .ic {{ width: 1.1em; height: 1.1em; color: var(--text-2); }}
    .menu-item .menu-check {{ margin-left: auto; color: var(--accent); }}

    /* ── Gallery view ── */
    /* A photo-first grid for showing off the plants: one tile per plant (its
       newest photo), no care chores anywhere. Tapping a tile opens the
       full-screen viewer in slideshow mode — swipe to keep browsing. */
    #gallery-scroll {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
                       padding: .8rem .8rem calc(.8rem + env(safe-area-inset-bottom)); }}
    .gal-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: .7rem;
                 max-width: 1200px; margin: 0 auto; }}
    @media (min-width: 720px) {{
      .gal-grid {{ grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: .9rem; }}
    }}
    .gal-card {{ position: relative; aspect-ratio: 3 / 4; border-radius: var(--radius);
                 overflow: hidden; background: var(--surface-2);
                 border: 1px solid var(--border); box-shadow: var(--shadow);
                 cursor: pointer; transition: transform .12s ease;
                 display: flex; align-items: center; justify-content: center; }}
    .gal-card:active {{ transform: scale(.97); }}
    .gal-card > .ic {{ width: 34px; height: 34px; color: var(--text-3); }}
    .gal-card img {{ position: absolute; inset: 0; width: 100%; height: 100%;
                     object-fit: cover; display: block; }}
    .gal-name {{ position: absolute; left: 0; right: 0; bottom: 0; z-index: 1;
                 padding: 1.6rem .65rem .55rem;
                 background: linear-gradient(transparent, rgba(0,0,0,.68));
                 color: #fff; font-weight: 700; font-size: .88rem; letter-spacing: -.01em;
                 white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .gal-empty {{ padding: 3.5rem 1.5rem; text-align: center; color: var(--text-2);
                  font-size: .9rem; grid-column: 1 / -1; }}

    /* ── Full-screen photo viewer (lightbox) ── */
    .lightbox {{ position: fixed; inset: 0; z-index: 100; background: rgba(0,0,0,.94);
                 opacity: 0; pointer-events: none; transition: opacity .2s ease;
                 overflow: hidden; touch-action: none; overscroll-behavior: contain; }}
    .lightbox.show {{ opacity: 1; pointer-events: auto; }}
    .lightbox img {{ position: absolute; inset: 0; width: 100%; height: 100%;
                     object-fit: contain; transform-origin: 0 0; will-change: transform;
                     user-select: none; -webkit-user-drag: none; }}
    .lb-close {{ position: fixed; top: calc(.55rem + env(safe-area-inset-top)); right: .7rem;
                 width: 42px; height: 42px; border-radius: 50%; border: none; z-index: 101;
                 background: rgba(255,255,255,.18); color: #fff; font-size: 1.25rem;
                 cursor: pointer; display: flex; align-items: center; justify-content: center; }}
    .lb-close:active {{ background: rgba(255,255,255,.34); }}
    .lb-hint {{ position: fixed; left: 50%; transform: translateX(-50%); z-index: 101;
                bottom: calc(1rem + env(safe-area-inset-bottom)); pointer-events: none;
                color: rgba(255,255,255,.72); font-size: .76rem; font-weight: 600;
                background: rgba(0,0,0,.4); padding: .35rem .8rem; border-radius: var(--radius-pill);
                transition: opacity .3s ease; }}
    /* Slideshow chrome (only shown when the viewer is opened from the gallery):
       a caption naming the plant, ←/→ arrows to change plant, and ↑/↓ arrows to
       move through the plant's photo history (newest at the top, older below). */
    .lb-cap {{ position: fixed; top: calc(.9rem + env(safe-area-inset-top)); left: 50%;
               transform: translateX(-50%); z-index: 101; pointer-events: none;
               max-width: calc(100% - 7.5rem); white-space: nowrap; overflow: hidden;
               text-overflow: ellipsis; color: #fff; font-size: .85rem; font-weight: 700;
               background: rgba(0,0,0,.45); padding: .4rem .9rem;
               border-radius: var(--radius-pill); }}
    .lb-nav {{ position: fixed; z-index: 101;
               width: 42px; height: 42px; border-radius: 50%; border: none;
               background: rgba(255,255,255,.18); color: #fff; font-size: 1.2rem;
               cursor: pointer; display: flex; align-items: center; justify-content: center; }}
    .lb-nav:active {{ background: rgba(255,255,255,.34); }}
    .lb-prev {{ left: .7rem; top: 50%; transform: translateY(-50%); }}
    .lb-next {{ right: .7rem; top: 50%; transform: translateY(-50%); }}
    .lb-up   {{ left: 50%; transform: translateX(-50%); top: calc(3.6rem + env(safe-area-inset-top)); }}
    .lb-down {{ left: 50%; transform: translateX(-50%); bottom: calc(3.6rem + env(safe-area-inset-bottom)); }}

    /* ── Check-off toggles (list rows) ── */
    .chk {{ width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0;
            border: 1.5px solid var(--border); background: var(--surface-2); font-size: 1rem;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; opacity: .5; filter: grayscale(1);
            transition: opacity .15s, filter .15s, box-shadow .15s, background .15s, transform .1s; }}
    .chk:active {{ transform: scale(.9); }}
    /* A button this plant needs today: orange, drawing the eye. */
    .chk.need {{ opacity: 1; filter: none; background: var(--warn-bg); color: var(--warn-text);
                 border-color: var(--warn); box-shadow: inset 0 0 0 1.5px var(--warn); }}
    /* Checked off as done (watered / fertilized): green. */
    .chk.done {{ opacity: 1; filter: none; background: var(--ok-bg); color: var(--ok-text);
                 border-color: var(--ok); box-shadow: inset 0 0 0 2px var(--ok); }}
    /* Soil checked but still wet: a neutral "snoozed/delayed" state, not a
       completion — gray so it reads differently from the green done states. */
    .chk.snooze {{ opacity: 1; filter: none; background: var(--paused-bg); color: var(--paused-text);
                   border-color: var(--paused); box-shadow: inset 0 0 0 2px var(--paused); }}
    /* Feed is overdue but waiting on the next watering — informational, not an
       attention item. A calm blue highlight on the sprout button carries that
       data in the "All good" section without a layout-disrupting chip (and reads
       distinctly from the orange "needs attention" state). */
    .chk.pending {{ opacity: 1; filter: none; background: var(--info-bg); color: var(--info-text);
                    border-color: var(--info); box-shadow: inset 0 0 0 1.5px var(--info); }}

    /* ── Action bar (list view) ── */
    .action-bar {{ flex-shrink: 0; display: flex; align-items: center; gap: .75rem;
                   background: var(--surface); border-top: 1px solid var(--border);
                   padding: .7rem 1rem calc(.7rem + env(safe-area-inset-bottom));
                   box-shadow: var(--shadow-up); }}
    .bar-count {{ flex: 1; font-size: .8rem; font-weight: 500; color: var(--text-2);
                  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .clear-btn {{ background: none; border: none; color: var(--text-2);
                  font-size: .8rem; cursor: pointer; flex-shrink: 0; padding: .3rem .2rem; }}
    .clear-btn:active {{ color: var(--text); }}
    .copy-btn {{ background: var(--accent); color: var(--on-accent); border: none;
                 border-radius: var(--radius-sm); padding: .62rem 1.2rem; font-size: .9rem;
                 font-weight: 800; letter-spacing: -.01em; cursor: pointer; flex-shrink: 0;
                 box-shadow: var(--accent-shadow); transition: transform .1s ease; }}
    .copy-btn:disabled {{ opacity: .4; box-shadow: none; pointer-events: none; }}
    .copy-btn:active {{ transform: scale(.96); background: var(--accent-press); }}

    /* ── Detail check-off buttons ── */
    .d-actions {{ display: flex; flex-wrap: wrap; gap: .55rem; margin-top: 1.1rem; }}
    .d-chk {{ flex: 1 1 30%; min-width: 96px; padding: .75rem .5rem; border-radius: var(--radius-sm);
              cursor: pointer; border: 1.5px solid var(--border); background: var(--surface-2);
              color: var(--text); font-size: .82rem; font-weight: 700; transition: transform .1s ease; }}
    .d-chk:active {{ transform: scale(.96); }}
    .d-chk.need {{ background: var(--warn); color: #fff; border-color: var(--warn); }}
    .d-chk.done {{ background: var(--ok-solid); color: #fff; border-color: var(--ok-solid); }}
    .d-chk.snooze {{ background: var(--paused); color: #fff; border-color: var(--paused); }}

    /* ── Toast ── */
    .toast {{ position: fixed; left: 50%; bottom: 5.5rem; z-index: 50;
              transform: translateX(-50%) translateY(20px);
              background: var(--toast-bg); color: var(--toast-text);
              padding: .75rem 1.2rem; border-radius: var(--radius-pill);
              font-size: .85rem; font-weight: 600; max-width: 80%;
              box-shadow: 0 8px 24px rgba(0,0,0,.25);
              opacity: 0; pointer-events: none; transition: opacity .25s, transform .25s; }}
    .toast.show {{ opacity: 1; transform: translateX(-50%) translateY(0); }}

    /* ── Slide animation ── */
    @keyframes fromRight {{ from {{ opacity:0; transform:translateX(36px) }} to {{ opacity:1; transform:translateX(0) }} }}
    @keyframes fromLeft  {{ from {{ opacity:0; transform:translateX(-36px) }} to {{ opacity:1; transform:translateX(0) }} }}
    .from-right {{ animation: fromRight .22s ease-out; }}
    .from-left  {{ animation: fromLeft  .22s ease-out; }}

    /* ── Wide screens (desktop browser) ── */
    /* The single-column list reads as a thin ribbon on a wide window, so here
       we flow the cards into a responsive multi-column tile grid. The section
       labels span the full width; each .row becomes a tile (it's already a
       self-contained card). Mobile keeps the stacked list above. */
    @media (min-width: 720px) {{
      #list-scroll {{ display: grid; align-content: start; align-items: start;
                      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                      gap: .8rem; padding: 1.2rem 1.4rem calc(1.2rem + .4rem);
                      max-width: 1200px; margin: 0 auto; width: 100%; }}
      .sec-label {{ grid-column: 1 / -1; padding: .9rem .2rem .1rem; }}
      .row {{ margin: 0; }}

      #detail-scroll {{ padding: 1.6rem 1.6rem 6rem; }}
      .d-body {{ display: flex; align-items: flex-start; gap: 1.8rem;
                 max-width: 1100px; margin: 0 auto; }}
      .gallery {{ flex: 0 0 48%; max-width: 480px; margin-bottom: 0;
                  position: sticky; top: 0; }}
      .plant-photo {{ height: auto; max-height: 78vh; object-fit: contain; }}
      .d-content {{ flex: 1 1 0; min-width: 0; }}
    }}
  </style>
</head>
<body>

<!-- List view -->
<div class="view" id="list-view">
  <div class="hdr">
    <span class="hdr-title">{icon('leaf')} Plant Care</span>
    <span class="hdr-sub">{short_date}</span>
    <div class="menu-wrap">
      <button class="back-btn icon-btn" id="menu-btn" aria-label="Menu" aria-haspopup="true">{icon('menu')}</button>
      <div class="menu-pop hidden" id="menu-pop">
        <button class="menu-item" id="menu-care">{icon('list-checks')} Care checklist <span class="menu-check">{icon('check')}</span></button>
        <button class="menu-item" id="menu-gallery">{icon('images')} Plant gallery</button>
      </div>
    </div>
  </div>
  <div id="list-scroll"></div>
  <div class="action-bar" id="action-bar">
    <span class="bar-count" id="bar-count">Tap {icon('droplet')} / {icon('droplets')} / {icon('sprout')} to check off as you go</span>
    <button class="clear-btn hidden" id="clear-btn">Clear selections</button>
    <button class="copy-btn" id="copy-btn" disabled>{icon('clipboard')} Copy</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<!-- Full-screen zoomable photo viewer -->
<div class="lightbox" id="lightbox" aria-hidden="true">
  <img id="lb-img" alt="">
  <button class="lb-close" id="lb-close" aria-label="Close photo">{icon('x')}</button>
  <div class="lb-cap hidden" id="lb-cap"></div>
  <button class="lb-nav lb-prev hidden" id="lb-prev" aria-label="Previous plant">{icon('chevron-left')}</button>
  <button class="lb-nav lb-next hidden" id="lb-next" aria-label="Next plant">{icon('chevron-right')}</button>
  <button class="lb-nav lb-up hidden" id="lb-up" aria-label="Newer photo">{icon('chevron-up')}</button>
  <button class="lb-nav lb-down hidden" id="lb-down" aria-label="Older photo">{icon('chevron-down')}</button>
  <div class="lb-hint" id="lb-hint">Pinch, double-tap, or scroll to zoom</div>
</div>

<!-- Gallery view: photo-first, no care chores — for handing the phone over -->
<div class="view hidden" id="gallery-view">
  <div class="hdr">
    <button class="back-btn" id="gal-back-btn">{icon('arrow-left')} List</button>
    <span class="hdr-title">{icon('images')} Plant Gallery</span>
    <span class="hdr-sub" id="gal-sub"></span>
  </div>
  <div id="gallery-scroll"></div>
</div>

<!-- Detail view -->
<div class="view hidden" id="detail-view">
  <div class="hdr">
    <button class="back-btn" id="back-btn">{icon('arrow-left')} List</button>
    <span class="hdr-title" id="d-title"></span>
    <button class="back-btn icon-btn" id="link-btn" aria-label="Copy link to this plant" title="Copy link">{icon('link')}</button>
    <span class="hdr-sub" id="d-counter"></span>
  </div>
  <div id="detail-scroll"></div>
  <div class="d-nav" id="d-nav">
    <button class="nav-btn" id="prev-btn">{icon('arrow-left')}</button>
    <span class="nav-hint" id="nav-hint"></span>
    <button class="nav-btn" id="next-btn">{icon('arrow-right')}</button>
  </div>
</div>

<script>
const P = {plants_json};
let cur = 0;

// ── Inline Lucide icons (mirrors the Python ICON_PATHS map) ──
const ICONS = {icons_json};
function icon(name, cls) {{
  return '<svg class="ic ' + (cls || '') + '" viewBox="0 0 24 24" fill="none" '
       + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
       + 'stroke-linejoin="round" aria-hidden="true">' + ICONS[name] + '</svg>';
}}
// Drop a leaf icon into an avatar tile when its photo fails to load.
function avatarFallback(el) {{ el.classList.remove('cut'); el.innerHTML = icon('leaf'); }}

// ── Check-off state (persisted per-day) ──
const TODAY = "{today.isoformat()}";
const SUMMARY_DATE = "{short_date}";
const SKEY = 'pc-actions-' + TODAY;
let actions = {{}};
try {{ actions = JSON.parse(localStorage.getItem(SKEY)) || {{}}; }} catch (e) {{ actions = {{}}; }}

function getA(name) {{ return actions[name] || {{w: false, wet: false, f: false}}; }}
function toggleA(name, key) {{
  const a = getA(name);
  const nv = !a[key];
  a[key] = nv;
  // Watered and "soil still wet" are mutually exclusive outcomes of one check.
  if (nv && key === 'w') a.wet = false;
  if (nv && key === 'wet') a.w = false;
  actions[name] = a;
  try {{ localStorage.setItem(SKEY, JSON.stringify(actions)); }} catch (e) {{}}
  updateBar();
  return nv;
}}

// ── List ──
function buildList() {{
  const urgent = P.filter(p => p.hasAction);
  const ok     = P.filter(p => !p.hasAction);
  let h = '';
  if (urgent.length) {{
    h += `<div class="sec-label warn">${{icon('triangle-alert')}} Needs attention (${{urgent.length}})</div>`;
    urgent.forEach((p, i) => h += rowHTML(p, i));
  }}
  if (ok.length) {{
    h += `<div class="sec-label">${{icon('circle-check')}} All good (${{ok.length}})</div>`;
    ok.forEach((p, i) => h += rowHTML(p, urgent.length + i));
  }}
  const el = document.getElementById('list-scroll');
  const prevScroll = el.scrollTop;
  el.innerHTML = h;
  el.querySelectorAll('.chk').forEach(b => b.addEventListener('click', e => {{
    e.stopPropagation();
    toggleA(P[+b.dataset.i].name, b.dataset.act);
    buildList();  // rebuild so mutually-exclusive siblings refresh
  }}));
  el.querySelectorAll('.row').forEach(r =>
    r.addEventListener('click', () => openDetail(+r.dataset.i))
  );
  el.scrollTop = prevScroll;
  updateBar();
}}

function rowHTML(p, i) {{
  const loc = p.location ? `<div class="row-loc">${{icon('map-pin')}} ${{p.location}}</div>` : '';
  const a = getA(p.name);
  // What does this plant need today? Drives both the chips and which buttons glow.
  const waterNeed = p.waterStatus === 'check';
  const noRecord  = p.waterStatus === 'unknown';
  const fertNeed  = p.fertStatus === 'due';
  const fertPending = p.fertStatus === 'pending';

  const chips = [];
  if (waterNeed) chips.push(`<span class="need-chip water">${{icon('droplet')}} Soil check due</span>`);
  if (noRecord)  chips.push(`<span class="need-chip unknown">${{icon('droplet')}} No water record</span>`);
  if (fertNeed)  chips.push(`<span class="need-chip fert">${{icon('sprout')}} Feed due</span>`);
  // A pending feed (overdue but waiting on the next watering) is an "All good"
  // plant — we skip the long "Feed at next watering" chip (it wraps and
  // disrupts the row layout) and instead highlight the sprout button below.
  const needs = chips.length ? `<div class="row-needs">${{chips.join('')}}</div>` : '';

  // Thumbnail. A background-removed cutout (p.thumb), when available, floats on
  // the card color — so no leaf sits behind it (it would show through the
  // transparent areas); if it fails to load we drop in the leaf instead.
  // Otherwise the newest photo fills the tile over a leaf fallback.
  const photos = p.photos || [];
  const latest = photos.length ? photos[photos.length - 1] : null;
  let avatar;
  if (p.thumb) {{
    avatar = `<div class="row-avatar cut"><img src="${{p.thumb}}" alt="" loading="lazy" onerror="avatarFallback(this.parentNode)"></div>`;
  }} else if (latest) {{
    avatar = `<div class="row-avatar">${{icon('leaf')}}<img src="${{latest.src}}" alt="" loading="lazy" onerror="this.remove()"></div>`;
  }} else {{
    avatar = `<div class="row-avatar">${{icon('leaf')}}</div>`;
  }}

  // Orange = needs attention, green = checked off. Once one of the water pair
  // (watered / soil-still-wet) is checked, the other drops to neutral.
  const cls = (act, done) => {{
    let c = 'chk' + (act === 'wet' ? ' wet' : '');
    if (done) return c + (act === 'wet' ? ' snooze' : ' done');
    if (act === 'w' && a.wet) return c;
    if (act === 'wet' && a.w) return c;
    if ((act === 'w' || act === 'wet') && (waterNeed || noRecord)) c += ' need';
    if (act === 'f' && fertNeed) c += ' need';
    // Pending feed: calm blue highlight instead of the orange "need" alarm.
    if (act === 'f' && fertPending) c += ' pending';
    return c;
  }};
  // With the chip gone, let the sprout button's tooltip carry the pending detail.
  const fertTitle = fertPending ? 'Feed due at next watering' : 'Fertilized';

  // Only surface the action icons a plant actually needs. An "All good" plant
  // (no attention item) needs no watering today — otherwise it would sit under
  // "Needs attention" — so we drop the two water buttons there and keep the
  // sprout only when a feed is waiting on the next watering (or already ticked).
  const waterBtns =
      `<button class="${{cls('w', a.w)}}" data-i="${{i}}" data-act="w" aria-label="Mark watered" title="Watered">${{icon('droplet')}}</button>`
    + `<button class="${{cls('wet', a.wet)}}" data-i="${{i}}" data-act="wet" aria-label="Soil still wet" title="Checked — soil still wet">${{icon('droplets')}}</button>`;
  const fertBtn =
      `<button class="${{cls('f', a.f)}}" data-i="${{i}}" data-act="f" aria-label="${{fertTitle}}" title="${{fertTitle}}">${{icon('sprout')}}</button>`;
  const dots = p.hasAction ? (waterBtns + fertBtn) : ((fertPending || a.f) ? fertBtn : '');
  const dotsHTML = dots ? `<div class="row-dots">${{dots}}</div>` : '';

  return `<div class="row${{p.hasAction ? ' urgent' : ''}}" data-i="${{i}}">
  ${{avatar}}
  <div class="row-info">
    <div class="row-name">${{p.nickname || p.name}}</div>${{loc}}${{needs}}
  </div>
  ${{dotsHTML}}
  <div class="chevron">${{icon('chevron-right')}}</div>
</div>`;
}}

// ── Detail ──
// Each plant has a stable `id` (its care-log key). We mirror the open plant
// into the URL hash (e.g. #money-tree) so a detail page is directly
// shareable / bookmarkable and the browser back button works.
function plantIndexById(id) {{
  for (let i = 0; i < P.length; i++) if (P[i].id === id) return i;
  return -1;
}}

function detailShown() {{
  return !document.getElementById('detail-view').classList.contains('hidden');
}}

function galleryShown() {{
  return !document.getElementById('gallery-view').classList.contains('hidden');
}}

function showDetail(i, dir) {{
  document.getElementById('list-view').classList.add('hidden');
  document.getElementById('gallery-view').classList.add('hidden');
  document.getElementById('detail-view').classList.remove('hidden');
  renderDetail(i, dir);  // sets cur = i
}}

function showList() {{
  document.getElementById('detail-view').classList.add('hidden');
  document.getElementById('gallery-view').classList.add('hidden');
  document.getElementById('list-view').classList.remove('hidden');
  buildList();
}}

function showGallery() {{
  document.getElementById('list-view').classList.add('hidden');
  document.getElementById('detail-view').classList.add('hidden');
  document.getElementById('gallery-view').classList.remove('hidden');
  buildGallery();
}}

// Open a plant by writing the hash; the hashchange handler does the rendering,
// which keeps a real history entry so back returns to the list.
function openDetail(i) {{
  location.hash = encodeURIComponent(P[i].id);
}}

// Drive the visible view from the current URL hash. `#gallery` is a reserved
// hash for the gallery view; anything else is a plant id (detail view).
function applyHash() {{
  const id = decodeURIComponent(location.hash.slice(1));
  if (id === 'gallery') {{
    if (!galleryShown()) showGallery();
    return;
  }}
  const i = id ? plantIndexById(id) : -1;
  if (i >= 0) {{
    if (!detailShown() || cur !== i) showDetail(i, 0);
  }} else if (detailShown() || galleryShown()) {{
    showList();
  }}
}}
window.addEventListener('hashchange', applyHash);

function renderDetail(i, dir) {{
  cur = i;
  const p = P[i];
  document.getElementById('d-title').textContent = p.nickname || p.name;
  document.getElementById('d-counter').textContent = `${{i + 1}} / ${{P.length}}`;
  document.getElementById('prev-btn').disabled = i === 0;
  document.getElementById('next-btn').disabled = i === P.length - 1;

  // Hint between the ← / → buttons. A bare name is ambiguous (next? previous?),
  // so label it directionally: normally it previews the next plant; on the last
  // plant the → is disabled, so it points back to the previous one instead.
  const nextP = P[i + 1], prevP = P[i - 1];
  const nextName = n => n.nickname || n.name;
  document.getElementById('nav-hint').textContent =
    nextP ? `Next: ${{nextName(nextP)}} →`
          : (prevP ? `← Prev: ${{nextName(prevP)}}` : '');

  const notesHTML = p.notes && p.notes.length
    ? `<div class="notes"><strong>${{icon('lightbulb')}} Notes</strong><ul>${{
        p.notes.map(n => `<li>${{n}}</li>`).join('')}}</ul></div>`
    : '';

  const photoHTML = galleryHTML(p);

  const dLabels = {{
    w:   {{icon: 'droplet',  on: 'Watered',        off: 'Mark watered'}},
    wet: {{icon: 'droplets', on: 'Soil still wet', off: 'Soil still wet'}},
    f:   {{icon: 'sprout',   on: 'Fertilized',     off: 'Mark fertilized'}},
  }};
  const a = getA(p.name);
  const waterNeed = p.waterStatus === 'check' || p.waterStatus === 'unknown';
  const fertNeed  = p.fertStatus === 'due';
  // Same rules as the list: orange = needs attention, green = checked off,
  // and the unchosen half of the water pair stays neutral.
  const dCls = k => {{
    if (a[k]) return 'd-chk ' + (k === 'wet' ? 'snooze' : 'done');
    if (k === 'w' && a.wet) return 'd-chk';
    if (k === 'wet' && a.w) return 'd-chk';
    if ((k === 'w' || k === 'wet') && waterNeed) return 'd-chk need';
    if (k === 'f' && fertNeed) return 'd-chk need';
    return 'd-chk';
  }};
  const dBtn = k => {{
    const l = dLabels[k];
    const tail = a[k] ? ' ' + icon('check') : '';
    return `<button class="${{dCls(k)}}" data-act="${{k}}">${{icon(l.icon)}} ${{a[k] ? l.on : l.off}}${{tail}}</button>`;
  }};
  const actionsHTML = `<div class="d-actions">${{dBtn('w')}}${{dBtn('wet')}}${{dBtn('f')}}</div>`;

  const animClass = dir > 0 ? 'from-right' : dir < 0 ? 'from-left' : '';
  const scr = document.getElementById('detail-scroll');
  scr.innerHTML = `<div class="${{animClass}} d-body">
    ${{photoHTML}}
    <div class="d-content">
      <div class="d-name">${{p.name}}</div>
      ${{p.location ? `<div class="d-loc">${{icon('map-pin')}} ${{p.location}}</div>` : ''}}
      <div class="badge ${{p.waterStatus}}">${{icon('droplet')}} ${{p.waterMsg}}</div>
      <div class="badge ${{p.fertStatus}}">${{icon('sprout')}} ${{p.fertMsg}}</div>
      ${{actionsHTML}}
      ${{notesHTML}}
    </div>
  </div>`;
  scr.scrollTop = 0;
  initGallery(scr);

  // Tapping a photo (or its maximize button) opens the full-screen zoomable viewer.
  scr.querySelectorAll('.plant-photo').forEach(im =>
    im.addEventListener('click', () => openLightbox(im.src, im.alt))
  );
  scr.querySelectorAll('.g-zoom').forEach(b => b.addEventListener('click', e => {{
    e.stopPropagation();
    openLightbox(b.dataset.src, '');
  }}));

  scr.querySelectorAll('.d-chk').forEach(b => b.addEventListener('click', () => {{
    toggleA(p.name, b.dataset.act);
    renderDetail(i, 0);  // re-render so mutually-exclusive buttons refresh
  }}));
}}

// ── Photo gallery (per plant) ──
function galleryHTML(p) {{
  const photos = p.photos || [];
  if (!photos.length) return '';
  const slides = photos.map(ph => `<div class="slide">
      <img class="plant-photo" src="${{ph.src}}" alt="${{p.name}}"
           onerror="this.closest('.slide').style.display='none'">
      <button class="g-zoom" type="button" aria-label="Maximize photo" data-src="${{ph.src}}">${{icon('maximize')}}</button>
      ${{ph.label ? `<span class="photo-date">${{ph.label}}</span>` : ''}}
    </div>`).join('');
  const multi = photos.length > 1;
  const nav = multi
    ? `<button class="g-nav g-prev" aria-label="Older photo">${{icon('chevron-left')}}</button>
       <button class="g-nav g-next" aria-label="Newer photo">${{icon('chevron-right')}}</button>
       <div class="g-dots">${{photos.map((_, i) => `<span class="g-dot" data-i="${{i}}"></span>`).join('')}}</div>`
    : '';
  return `<div class="gallery"><div class="gallery-track">${{slides}}</div>${{nav}}</div>`;
}}

function initGallery(root) {{
  const g = root.querySelector('.gallery');
  if (!g) return;
  const track = g.querySelector('.gallery-track');
  const slides = [...track.querySelectorAll('.slide')];
  if (slides.length < 2) return;
  const dots = [...g.querySelectorAll('.g-dot')];
  const prev = g.querySelector('.g-prev'), next = g.querySelector('.g-next');
  const curIdx = () => Math.round(track.scrollLeft / track.clientWidth);
  const goTo = idx => {{
    idx = Math.max(0, Math.min(slides.length - 1, idx));
    track.scrollTo({{left: idx * track.clientWidth, behavior: 'smooth'}});
  }};
  const sync = () => {{
    const i = curIdx();
    dots.forEach((d, j) => d.classList.toggle('active', j === i));
    prev.disabled = i === 0;             // leftmost = oldest
    next.disabled = i === slides.length - 1;  // rightmost = newest
  }};
  prev.addEventListener('click', () => goTo(curIdx() - 1));
  next.addEventListener('click', () => goTo(curIdx() + 1));
  dots.forEach(d => d.addEventListener('click', () => goTo(+d.dataset.i)));
  track.addEventListener('scroll', () => {{
    clearTimeout(track._t); track._t = setTimeout(sync, 60);
  }}, {{passive: true}});
  // Open focused on the latest photo (rightmost), then let the user scroll back.
  requestAnimationFrame(() => {{ track.scrollLeft = track.scrollWidth; sync(); }});
}}

// ── Gallery view (show-off mode) ──
// One tile per plant showing its newest photo — no chores, no status. Tapping
// a tile opens the full-screen viewer in slideshow mode: swipe sideways to
// move between plants (always landing on a plant's newest photo), swipe
// up/down to move through that plant's photo history (newest first, older
// photos "below").
function buildGallery() {{
  // P is ordered needs-attention-first for the checklist; that ordering is
  // meaningless (and shuffles daily) in a gallery, so sort by display name.
  const withPhotos = P.filter(p => (p.photos || []).length)
    .slice().sort((a, b) => (a.nickname || a.name).localeCompare(b.nickname || b.name));
  document.getElementById('gal-sub').textContent =
    `${{withPhotos.length}} plant${{withPhotos.length === 1 ? '' : 's'}}`;

  // Slideshow playlist: one entry per plant, photos newest → oldest.
  const playlist = withPhotos.map(p => ({{
    name: p.nickname || p.name,
    photos: [...p.photos].reverse().map(ph => ({{src: ph.src, label: ph.label}})),
  }}));

  const cards = withPhotos.map((p, i) => {{
    const latest = p.photos[p.photos.length - 1];
    return `<div class="gal-card" data-i="${{i}}">
      ${{icon('leaf')}}
      <img src="${{latest.src}}" alt="${{p.name}}" loading="lazy" onerror="this.remove()">
      <div class="gal-name">${{p.nickname || p.name}}</div>
    </div>`;
  }}).join('');

  const el = document.getElementById('gallery-scroll');
  el.innerHTML = `<div class="gal-grid">${{
    cards || '<div class="gal-empty">No photos yet — add one and it will show up here.</div>'
  }}</div>`;
  el.querySelectorAll('.gal-card').forEach(c =>
    c.addEventListener('click', () => openLightboxList(playlist, +c.dataset.i))
  );
}}

// ── Header sub menu ──
const menuPop = document.getElementById('menu-pop');
document.getElementById('menu-btn').addEventListener('click', e => {{
  e.stopPropagation();
  menuPop.classList.toggle('hidden');
}});
document.addEventListener('click', e => {{
  if (!menuPop.classList.contains('hidden') && !e.target.closest('.menu-wrap'))
    menuPop.classList.add('hidden');
}});
document.getElementById('menu-care').addEventListener('click', () =>
  menuPop.classList.add('hidden')  // already on the checklist
);
document.getElementById('menu-gallery').addEventListener('click', () => {{
  menuPop.classList.add('hidden');
  location.hash = 'gallery';  // hashchange handler renders the gallery
}});
document.getElementById('gal-back-btn').addEventListener('click', () => {{
  // Same pattern as the detail back button: clear the hash, show the list.
  if (location.hash) history.replaceState(null, '', location.pathname + location.search);
  showList();
}});

function goTo(i, dir) {{
  if (i < 0 || i >= P.length) return;
  renderDetail(i, dir);  // animate first (sets cur = i)…
  // …then sync the hash. cur is already i, so the resulting hashchange is a
  // no-op — this just keeps the URL shareable without re-rendering.
  const h = encodeURIComponent(P[i].id);
  if (location.hash.slice(1) !== h) location.hash = h;
}}

// ── Action bar: copy / clear ──
function checkedNames() {{
  const watered = [], stillWet = [], fed = [];
  P.forEach(p => {{
    const a = getA(p.name);
    if (a.w) watered.push(p.name);
    if (a.wet) stillWet.push(p.name);
    if (a.f) fed.push(p.name);
  }});
  return {{watered, stillWet, fed}};
}}

function updateBar() {{
  const {{watered, stillWet, fed}} = checkedNames();
  const total = watered.length + stillWet.length + fed.length;
  const count = document.getElementById('bar-count');
  if (total === 0) {{
    count.innerHTML = `Tap ${{icon('droplet')}} / ${{icon('droplets')}} / ${{icon('sprout')}} to check off as you go`;
  }} else {{
    const parts = [];
    if (watered.length) parts.push(`${{icon('droplet')}} ${{watered.length}} watered`);
    if (stillWet.length) parts.push(`${{icon('droplets')}} ${{stillWet.length}} still wet`);
    if (fed.length) parts.push(`${{icon('sprout')}} ${{fed.length}} fertilized`);
    count.innerHTML = parts.join('  ·  ');
  }}
  const copyBtn = document.getElementById('copy-btn');
  copyBtn.disabled = total === 0;
  copyBtn.innerHTML = total > 0 ? `${{icon('clipboard')}} Copy ${{total}}` : `${{icon('clipboard')}} Copy`;
  document.getElementById('clear-btn').classList.toggle('hidden', total === 0);
}}

function buildSummary() {{
  const {{watered, stillWet, fed}} = checkedNames();
  const lines = [`Plant care — ${{SUMMARY_DATE}}`, ''];
  if (watered.length) {{
    lines.push('Watered:');
    watered.forEach(n => lines.push(`- ${{n}}`));
    lines.push('');
  }}
  if (stillWet.length) {{
    lines.push('Soil checked — still wet, skipped watering:');
    stillWet.forEach(n => lines.push(`- ${{n}}`));
    lines.push('');
  }}
  if (fed.length) {{
    lines.push('Fertilized:');
    fed.forEach(n => lines.push(`- ${{n}}`));
    lines.push('');
  }}
  return lines.join('\\n').trim();
}}

function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 2200);
}}

function copyText(text) {{
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    return navigator.clipboard.writeText(text);
  }}
  return new Promise((resolve, reject) => {{
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {{ document.execCommand('copy'); resolve(); }}
    catch (e) {{ reject(e); }}
    finally {{ document.body.removeChild(ta); }}
  }});
}}

document.getElementById('copy-btn').addEventListener('click', () => {{
  const text = buildSummary();
  if (!text) return;
  copyText(text)
    .then(() => showToast('Copied to clipboard'))
    .catch(() => showToast('Copy failed — long-press to select'));
}});

document.getElementById('clear-btn').addEventListener('click', () => {{
  actions = {{}};
  try {{ localStorage.removeItem(SKEY); }} catch (e) {{}}
  buildList();
}});

// ── Events ──
document.getElementById('back-btn').addEventListener('click', () => {{
  // Drop the plant from the URL; the hashchange handler returns to the list.
  // If there's no hash (deep-linked straight to a detail), switch directly.
  if (location.hash) history.replaceState(null, '', location.pathname + location.search);
  showList();
}});
// Copy a shareable deep link to the plant currently shown in the detail view.
document.getElementById('link-btn').addEventListener('click', () => {{
  const url = location.origin + location.pathname + location.search
            + '#' + encodeURIComponent(P[cur].id);
  copyText(url)
    .then(() => showToast('Link copied'))
    .catch(() => showToast('Copy failed — long-press to select'));
}});
document.getElementById('prev-btn').addEventListener('click', () => goTo(cur - 1, -1));
document.getElementById('next-btn').addEventListener('click', () => goTo(cur + 1,  1));

// Swipe (horizontal > vertical and > 50px threshold).
// Swipe right returns to the list view; swipe left does nothing.
// Use the on-screen ← / → buttons to page through plants.
let tx = 0, ty = 0;
const scr = document.getElementById('detail-scroll');
scr.addEventListener('touchstart', e => {{
  tx = e.touches[0].clientX; ty = e.touches[0].clientY;
}}, {{passive: true}});
scr.addEventListener('touchend', e => {{
  if (e.target.closest('.gallery')) return;  // photo carousel owns horizontal swipes
  const dx = e.changedTouches[0].clientX - tx;
  const dy = e.changedTouches[0].clientY - ty;
  if (Math.abs(dx) > Math.abs(dy) * 1.5 && Math.abs(dx) > 50 && dx > 0)
    document.getElementById('back-btn').click();  // swipe right → back to list
}}, {{passive: true}});

// Arrow keys / Escape
document.addEventListener('keydown', e => {{
  // While the full-screen photo viewer is up, Escape closes it and the arrows
  // step the slideshow (a no-op on a single photo). Other keys are swallowed
  // so they don't page the underlying detail view.
  const lb = document.getElementById('lightbox');
  if (lb.isShown && lb.isShown()) {{
    if (e.key === 'Escape')     lb.close();
    if (e.key === 'ArrowRight') lb.nav(1);
    if (e.key === 'ArrowLeft')  lb.nav(-1);
    if (e.key === 'ArrowUp')    lb.navV(-1);   // newer
    if (e.key === 'ArrowDown')  lb.navV(1);    // older
    return;
  }}
  if (galleryShown()) {{
    if (e.key === 'Escape') document.getElementById('gal-back-btn').click();
    return;
  }}
  if (document.getElementById('detail-view').classList.contains('hidden')) return;
  if (e.key === 'ArrowRight') goTo(cur + 1,  1);
  if (e.key === 'ArrowLeft')  goTo(cur - 1, -1);
  if (e.key === 'Escape')     document.getElementById('back-btn').click();
}});

// ── Full-screen zoomable photo viewer ──
// Transform-based pan/zoom. The <img> fills the overlay (object-fit: contain)
// with transform-origin 0 0, so viewport coords map straight to the element and
// the focal-point zoom math stays simple. Supports pinch (touch), wheel and
// double-tap/double-click to zoom, and drag to pan while zoomed.
const LB = (() => {{
  const lb = document.getElementById('lightbox');
  const img = document.getElementById('lb-img');
  const hint = document.getElementById('lb-hint');
  const cap = document.getElementById('lb-cap');
  const prevB = document.getElementById('lb-prev');
  const nextB = document.getElementById('lb-next');
  const upB = document.getElementById('lb-up');
  const downB = document.getElementById('lb-down');
  const MIN = 1, MAX = 6;
  let scale = 1, tx = 0, ty = 0;
  const pts = new Map();              // active pointers
  let pinchDist = 0, pinchScale = 1;  // gesture baselines
  let lastTap = 0;
  // Slideshow mode (opened from the gallery): a playlist of plants, each with
  // its photos newest → oldest. `li` picks the plant (horizontal axis), `pi`
  // the photo within its history (vertical axis; 0 = newest, older "below").
  // Null when opened on a single photo from the detail view.
  let list = null, li = 0, pi = 0;
  let swipe = null;                   // start point of a potential swipe

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const apply = () => {{ img.style.transform = `translate(${{tx}}px,${{ty}}px) scale(${{scale}})`; }};

  function clampPan() {{
    const W = lb.clientWidth, H = lb.clientHeight;
    const sw = W * scale, sh = H * scale;
    tx = sw <= W ? (W - sw) / 2 : clamp(tx, W - sw, 0);
    ty = sh <= H ? (H - sh) / 2 : clamp(ty, H - sh, 0);
  }}

  function zoomAt(factor, fx, fy) {{
    const ns = clamp(scale * factor, MIN, MAX);
    const f = ns / scale;
    tx = fx - (fx - tx) * f;
    ty = fy - (fy - ty) * f;
    scale = ns;
    clampPan();
    apply();
  }}

  function reset() {{ scale = 1; tx = 0; ty = 0; clampPan(); apply(); }}

  function updateNav() {{
    const nPhotos = list ? list[li].photos.length : 0;
    prevB.classList.toggle('hidden', !list || li === 0);
    nextB.classList.toggle('hidden', !list || li === list.length - 1);
    upB.classList.toggle('hidden', !list || pi === 0);
    downB.classList.toggle('hidden', !list || pi === nPhotos - 1);
  }}

  function setItem() {{
    const pl = list[li];
    const ph = pl.photos[pi];
    let text = pl.name;
    if (ph.label) text += ' · ' + ph.label;
    if (pl.photos.length > 1) text += ` · ${{pi + 1}}/${{pl.photos.length}}`;
    img.src = ph.src; img.alt = text;
    cap.textContent = text;
    cap.classList.remove('hidden');
    updateNav();
    reset();
  }}

  // Horizontal: change plant, always landing on its newest photo.
  function nav(d) {{
    if (!list) return;
    const n = li + d;
    if (n < 0 || n >= list.length) return;
    li = n; pi = 0;
    setItem();
  }}

  // Vertical: move through the current plant's history (+1 = older, "below").
  function navV(d) {{
    if (!list) return;
    const n = pi + d;
    if (n < 0 || n >= list[li].photos.length) return;
    pi = n;
    setItem();
  }}

  function present(hintText) {{
    hint.textContent = hintText;
    lb.classList.add('show');
    lb.setAttribute('aria-hidden', 'false');
    hint.style.opacity = '1';
    clearTimeout(hint._t);
    hint._t = setTimeout(() => {{ hint.style.opacity = '0'; }}, 2600);
  }}

  function open(src, alt) {{
    list = null;
    img.src = src; img.alt = alt || '';
    cap.classList.add('hidden');
    updateNav();
    reset();
    present('Pinch, double-tap, or scroll to zoom');
  }}

  function openList(arr, idx) {{
    if (!arr || !arr.length) return;
    list = arr;
    li = Math.max(0, Math.min(arr.length - 1, idx || 0));
    pi = 0;  // always open on the newest photo
    setItem();
    present('Swipe sideways for plants · up for older photos');
  }}

  function close() {{
    lb.classList.remove('show');
    lb.setAttribute('aria-hidden', 'true');
    pts.clear();
    swipe = null;
  }}
  lb.isShown = () => lb.classList.contains('show');
  lb.close = close;
  lb.nav = nav;
  lb.navV = navV;

  // Two-finger helpers.
  const two = () => [...pts.values()];
  const dist = () => {{ const [a, b] = two(); return Math.hypot(a.x - b.x, a.y - b.y); }};
  const mid  = () => {{ const [a, b] = two(); return {{x: (a.x + b.x) / 2, y: (a.y + b.y) / 2}}; }};

  lb.addEventListener('pointerdown', e => {{
    pts.set(e.pointerId, {{x: e.clientX, y: e.clientY}});
    // Arm a slideshow swipe only for a single, unzoomed touch.
    swipe = (list && pts.size === 1 && scale <= 1.05)
      ? {{x: e.clientX, y: e.clientY}} : null;
    try {{ lb.setPointerCapture(e.pointerId); }} catch (err) {{}}
    if (pts.size === 2) {{ pinchDist = dist(); pinchScale = scale; }}
  }});

  lb.addEventListener('pointermove', e => {{
    if (!pts.has(e.pointerId)) return;
    const prev = pts.get(e.pointerId);
    pts.set(e.pointerId, {{x: e.clientX, y: e.clientY}});
    if (pts.size === 2 && pinchDist) {{
      const m = mid();
      const target = pinchScale * (dist() / pinchDist);
      zoomAt(clamp(target, MIN, MAX) / scale, m.x, m.y);
    }} else if (pts.size === 1 && scale > 1) {{
      tx += e.clientX - prev.x;
      ty += e.clientY - prev.y;
      clampPan();
      apply();
    }}
  }});

  function endPointer(e) {{
    pts.delete(e.pointerId);
    if (pts.size < 2) pinchDist = 0;
  }}
  lb.addEventListener('pointerup', e => {{
    // Slideshow swipes: single unzoomed touch past a threshold. Horizontal
    // changes plant; vertical moves through the plant's history — swiping up
    // pulls the next-older photo into view (older photos sit "below").
    if (swipe && pts.size === 1 && scale <= 1.05) {{
      const dx = e.clientX - swipe.x, dy = e.clientY - swipe.y;
      if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.5) {{
        nav(dx < 0 ? 1 : -1);
        lastTap = 0;  // a swipe isn't a tap — don't feed double-tap zoom
      }} else if (Math.abs(dy) > 55 && Math.abs(dy) > Math.abs(dx) * 1.5) {{
        navV(dy < 0 ? 1 : -1);
        lastTap = 0;
      }}
    }}
    swipe = null;
    endPointer(e);
  }});
  lb.addEventListener('pointercancel', e => {{ swipe = null; endPointer(e); }});

  // Double-tap (touch) to toggle zoom around the tap point.
  lb.addEventListener('pointerup', e => {{
    if (e.pointerType === 'mouse') return;
    const now = Date.now();
    if (now - lastTap < 300) {{
      if (scale > 1.05) reset(); else zoomAt(3 / scale, e.clientX, e.clientY);
      lastTap = 0;
    }} else {{
      lastTap = now;
    }}
  }});

  img.addEventListener('dblclick', e => {{
    e.preventDefault();
    if (scale > 1.05) reset(); else zoomAt(3 / scale, e.clientX, e.clientY);
  }});

  lb.addEventListener('wheel', e => {{
    e.preventDefault();
    zoomAt(e.deltaY < 0 ? 1.18 : 1 / 1.18, e.clientX, e.clientY);
  }}, {{passive: false}});

  // Tap the backdrop (not the photo) to close.
  lb.addEventListener('click', e => {{ if (e.target === lb) close(); }});
  document.getElementById('lb-close').addEventListener('click', close);
  prevB.addEventListener('click', e => {{ e.stopPropagation(); nav(-1); }});
  nextB.addEventListener('click', e => {{ e.stopPropagation(); nav(1); }});
  upB.addEventListener('click', e => {{ e.stopPropagation(); navV(-1); }});
  downB.addEventListener('click', e => {{ e.stopPropagation(); navV(1); }});

  return {{open, openList}};
}})();
function openLightbox(src, alt) {{ LB.open(src, alt); }}
function openLightboxList(list, idx) {{ LB.openList(list, idx); }}

buildList();
applyHash();  // honor a shared/bookmarked #plant-id deep link on load
</script>
<script>
if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js');
</script>
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

    docs = OUTPUT.parent
    docs.mkdir(exist_ok=True)
    OUTPUT.write_text(render(results, today))
    print(f"Report written → {OUTPUT}")

    (docs / "manifest.json").write_text(json.dumps(MANIFEST, indent=2))
    print(f"Manifest written → {docs / 'manifest.json'}")

    (docs / "sw.js").write_text(_sw_js(str(today)))
    print(f"SW written → {docs / 'sw.js'}")

    for size, name in [(192, "icon-192.png"), (512, "icon-512.png")]:
        path = docs / name
        path.write_bytes(_make_icon_png(size))
        print(f"Icon written → {path}")


if __name__ == "__main__":
    main()
