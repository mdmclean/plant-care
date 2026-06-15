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
        fert = ("paused", "Feeding paused — not in active season")

    notes = plant.get("notes") or []
    if isinstance(notes, str):
        notes = [notes]

    return dict(
        name=name,
        location=location,
        photos=photo_list(plant),
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
        "name": r["name"],
        "location": r["location"],
        "photos": r["photos"],
        "waterStatus": r["water_status"],
        "waterMsg": r["water_msg"],
        "fertStatus": r["fert_status"],
        "fertMsg": r["fert_msg"],
        "notes": r["notes"],
        "hasAction": r["has_action"],
    } for r in ordered])

    day = today.strftime("%-d")
    short_date = today.strftime(f"%b {day}")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>🌿 Plant Care</title>
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
      --warn: #f59e0b; --warn-bg: #fff3df; --warn-text: #b45309;
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

    /* ── List ── */
    #list-scroll {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
                    padding-bottom: .4rem; }}
    .sec-label {{ font-size: .7rem; font-weight: 800; letter-spacing: .09em;
                  text-transform: uppercase; color: var(--text-2);
                  padding: 1.1rem 1.15rem .4rem; }}
    .row {{ position: relative; display: flex; align-items: center; gap: .7rem;
            background: var(--surface); border: 1px solid var(--border);
            margin: .45rem .8rem; border-radius: var(--radius);
            padding: .9rem 1rem; cursor: pointer; box-shadow: var(--shadow);
            transition: transform .12s ease, background .12s ease; }}
    .row:active {{ transform: scale(.988); background: var(--surface-2); }}
    .row.urgent::before {{ content: ''; position: absolute; left: 0; top: 13px; bottom: 13px;
                           width: 4px; border-radius: 0 4px 4px 0; background: var(--warn); }}
    .row-info {{ flex: 1; min-width: 0; }}
    .row-name {{ font-weight: 700; font-size: .96rem; letter-spacing: -.01em;
                 white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .row-loc {{ font-size: .76rem; color: var(--text-2); margin-top: .2rem; }}
    .row-dots {{ display: flex; gap: .35rem; flex-shrink: 0; }}
    .chevron {{ color: var(--text-3); font-size: 1.1rem; flex-shrink: 0; margin-left: .1rem; }}

    /* ── Detail ── */
    #detail-scroll {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
                      padding: 1.1rem .9rem 6rem; }}
    .d-loc {{ font-size: .82rem; color: var(--text-2); margin-bottom: 1rem; }}
    .badge {{ padding: .7rem .9rem; border-radius: var(--radius-sm); margin: .45rem 0;
              font-size: .875rem; line-height: 1.5; font-weight: 500; border-left: 3px solid; }}
    .badge.check   {{ background: var(--warn-bg);   color: var(--warn-text);   border-color: var(--warn); }}
    .badge.due     {{ background: var(--info-bg);   color: var(--info-text);   border-color: var(--info); }}
    .badge.ok      {{ background: var(--ok-bg);     color: var(--ok-text);     border-color: var(--ok); }}
    .badge.paused  {{ background: var(--paused-bg); color: var(--paused-text); border-color: var(--paused); }}
    .badge.unknown {{ background: var(--danger-bg); color: var(--danger-text); border-color: var(--danger); }}
    .notes {{ margin-top: 1rem; padding: .85rem .9rem; background: var(--note-bg);
              border-radius: var(--radius-sm); border-left: 3px solid var(--note-border);
              font-size: .82rem; color: var(--note-text); }}
    .notes strong {{ color: var(--text); }}
    .notes ul {{ margin-left: 1.1rem; margin-top: .35rem; }}
    .notes li {{ margin: .3rem 0; line-height: 1.45; }}

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

    /* ── Check-off toggles (list rows) ── */
    .chk {{ width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
            border: 1.5px solid var(--border); background: var(--surface-2); font-size: 1rem;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; opacity: .5; filter: grayscale(1);
            transition: opacity .15s, filter .15s, box-shadow .15s, background .15s, transform .1s; }}
    .chk:active {{ transform: scale(.9); }}
    .chk.done {{ opacity: 1; filter: none; background: var(--ok-bg);
                 border-color: var(--ok); box-shadow: inset 0 0 0 2px var(--ok); }}
    .chk.wet.done {{ background: var(--info-bg); border-color: var(--info);
                     box-shadow: inset 0 0 0 2px var(--info); }}

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
    .d-chk.done {{ background: var(--ok-solid); color: #fff; border-color: var(--ok-solid); }}
    .d-chk[data-act="wet"].done {{ background: var(--info-solid); border-color: var(--info-solid); }}

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
  </style>
</head>
<body>

<!-- List view -->
<div class="view" id="list-view">
  <div class="hdr">
    <span class="hdr-title">🌿 Plant Care</span>
    <span class="hdr-sub">{short_date}</span>
  </div>
  <div id="list-scroll"></div>
  <div class="action-bar" id="action-bar">
    <span class="bar-count" id="bar-count">Tap 💧 / 🚱 / 🌱 to check off as you go</span>
    <button class="clear-btn hidden" id="clear-btn">Clear</button>
    <button class="copy-btn" id="copy-btn" disabled>📋 Copy</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<!-- Detail view -->
<div class="view hidden" id="detail-view">
  <div class="hdr">
    <button class="back-btn" id="back-btn">&#8592; List</button>
    <span class="hdr-title" id="d-title"></span>
    <span class="hdr-sub" id="d-counter"></span>
  </div>
  <div id="detail-scroll"></div>
  <div class="d-nav" id="d-nav">
    <button class="nav-btn" id="prev-btn">&#8592;</button>
    <span class="nav-hint" id="nav-hint"></span>
    <button class="nav-btn" id="next-btn">&#8594;</button>
  </div>
</div>

<script>
const P = {plants_json};
let cur = 0;

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
    h += `<div class="sec-label">⚠️ Needs attention (${{urgent.length}})</div>`;
    urgent.forEach((p, i) => h += rowHTML(p, i));
  }}
  if (ok.length) {{
    h += `<div class="sec-label">✅ All good (${{ok.length}})</div>`;
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
  const loc = p.location ? `<div class="row-loc">📍 ${{p.location}}</div>` : '';
  const a = getA(p.name);
  return `<div class="row${{p.hasAction ? ' urgent' : ''}}" data-i="${{i}}">
  <div class="row-info">
    <div class="row-name">${{p.name}}</div>${{loc}}
  </div>
  <div class="row-dots">
    <button class="chk${{a.w ? ' done' : ''}}" data-i="${{i}}" data-act="w" aria-label="Mark watered" title="Watered">💧</button>
    <button class="chk wet${{a.wet ? ' done' : ''}}" data-i="${{i}}" data-act="wet" aria-label="Soil still wet" title="Checked — soil still wet">🚱</button>
    <button class="chk${{a.f ? ' done' : ''}}" data-i="${{i}}" data-act="f" aria-label="Mark fertilized" title="Fertilized">🌱</button>
  </div>
  <div class="chevron">›</div>
</div>`;
}}

// ── Detail ──
function openDetail(i) {{
  cur = i;
  document.getElementById('list-view').classList.add('hidden');
  document.getElementById('detail-view').classList.remove('hidden');
  renderDetail(i, 0);
}}

function renderDetail(i, dir) {{
  cur = i;
  const p = P[i];
  document.getElementById('d-title').textContent = p.name;
  document.getElementById('d-counter').textContent = `${{i + 1}} / ${{P.length}}`;
  document.getElementById('prev-btn').disabled = i === 0;
  document.getElementById('next-btn').disabled = i === P.length - 1;

  const adj = P[i + 1] || P[i - 1];
  document.getElementById('nav-hint').textContent =
    P[i + 1] ? P[i + 1].name : (P[i - 1] ? P[i - 1].name : '');

  const notesHTML = p.notes && p.notes.length
    ? `<div class="notes"><strong>💡 Notes</strong><ul>${{
        p.notes.map(n => `<li>${{n}}</li>`).join('')}}</ul></div>`
    : '';

  const photoHTML = galleryHTML(p);

  const dLabels = {{
    w:   {{on: '💧 Watered ✓',      off: '💧 Mark watered'}},
    wet: {{on: '🚱 Soil still wet ✓', off: '🚱 Soil still wet'}},
    f:   {{on: '🌱 Fertilized ✓',   off: '🌱 Mark fertilized'}},
  }};
  const a = getA(p.name);
  const dBtn = k => `<button class="d-chk${{a[k] ? ' done' : ''}}" data-act="${{k}}">${{a[k] ? dLabels[k].on : dLabels[k].off}}</button>`;
  const actionsHTML = `<div class="d-actions">${{dBtn('w')}}${{dBtn('wet')}}${{dBtn('f')}}</div>`;

  const animClass = dir > 0 ? 'from-right' : dir < 0 ? 'from-left' : '';
  const scr = document.getElementById('detail-scroll');
  scr.innerHTML = `<div class="${{animClass}}">
    ${{photoHTML}}
    ${{p.location ? `<div class="d-loc">📍 ${{p.location}}</div>` : ''}}
    <div class="badge ${{p.waterStatus}}">💧 ${{p.waterMsg}}</div>
    <div class="badge ${{p.fertStatus}}">🌱 ${{p.fertMsg}}</div>
    ${{actionsHTML}}
    ${{notesHTML}}
  </div>`;
  scr.scrollTop = 0;
  initGallery(scr);

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
      ${{ph.label ? `<span class="photo-date">${{ph.label}}</span>` : ''}}
    </div>`).join('');
  const multi = photos.length > 1;
  const nav = multi
    ? `<button class="g-nav g-prev" aria-label="Older photo">&#8249;</button>
       <button class="g-nav g-next" aria-label="Newer photo">&#8250;</button>
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

function goTo(i, dir) {{
  if (i < 0 || i >= P.length) return;
  renderDetail(i, dir);
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
    count.textContent = 'Tap 💧 / 🚱 / 🌱 to check off as you go';
  }} else {{
    const parts = [];
    if (watered.length) parts.push(`💧 ${{watered.length}} watered`);
    if (stillWet.length) parts.push(`🚱 ${{stillWet.length}} still wet`);
    if (fed.length) parts.push(`🌱 ${{fed.length}} fertilized`);
    count.textContent = parts.join('  ·  ');
  }}
  document.getElementById('copy-btn').disabled = total === 0;
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
    .then(() => showToast('📋 Copied — paste into your chat'))
    .catch(() => showToast('Copy failed — long-press to select'));
}});

document.getElementById('clear-btn').addEventListener('click', () => {{
  actions = {{}};
  try {{ localStorage.removeItem(SKEY); }} catch (e) {{}}
  buildList();
}});

// ── Events ──
document.getElementById('back-btn').addEventListener('click', () => {{
  document.getElementById('detail-view').classList.add('hidden');
  document.getElementById('list-view').classList.remove('hidden');
  buildList();
}});
document.getElementById('prev-btn').addEventListener('click', () => goTo(cur - 1, -1));
document.getElementById('next-btn').addEventListener('click', () => goTo(cur + 1,  1));

// Swipe (horizontal > vertical and > 50px threshold)
let tx = 0, ty = 0;
const scr = document.getElementById('detail-scroll');
scr.addEventListener('touchstart', e => {{
  tx = e.touches[0].clientX; ty = e.touches[0].clientY;
}}, {{passive: true}});
scr.addEventListener('touchend', e => {{
  if (e.target.closest('.gallery')) return;  // photo carousel owns horizontal swipes
  const dx = e.changedTouches[0].clientX - tx;
  const dy = e.changedTouches[0].clientY - ty;
  if (Math.abs(dx) > Math.abs(dy) * 1.5 && Math.abs(dx) > 50)
    goTo(dx < 0 ? cur + 1 : cur - 1, dx < 0 ? 1 : -1);
}}, {{passive: true}});

// Arrow keys / Escape
document.addEventListener('keydown', e => {{
  if (document.getElementById('detail-view').classList.contains('hidden')) return;
  if (e.key === 'ArrowRight') goTo(cur + 1,  1);
  if (e.key === 'ArrowLeft')  goTo(cur - 1, -1);
  if (e.key === 'Escape')     document.getElementById('back-btn').click();
}});

buildList();
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
