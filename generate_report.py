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
    "background_color": "#f1f8e9",
    "theme_color": "#2e7d32",
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
  <meta name="theme-color" content="#2e7d32">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Plant Care">
  <link rel="apple-touch-icon" href="icon-192.png">
  <style>
    :root {{
      --green-dk: #2e7d32; --green-md: #43a047; --green-bg: #f1f8e9;
      --orange: #e65100; --orange-bg: #fff3e0; --orange-border: #ff9800;
      --blue: #1565c0;   --blue-bg: #e3f2fd;   --blue-border: #2196f3;
      --ok: #2e7d32;     --ok-bg: #e8f5e9;     --ok-border: #4caf50;
      --gray: #757575;   --gray-bg: #f5f5f5;   --gray-border: #bdbdbd;
      --red-bg: #fce4ec; --red: #880e4f;       --red-border: #e91e63;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }}
    html, body {{ height: 100%; overflow: hidden; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--green-bg); color: #1b1b1b; }}

    /* ── Views ── */
    .view {{ position: fixed; inset: 0; display: flex; flex-direction: column;
             transition: transform .25s ease, opacity .25s ease; }}
    .view.hidden {{ display: none; }}

    /* ── Header ── */
    .hdr {{ background: linear-gradient(135deg, var(--green-dk), var(--green-md));
            color: #fff; display: flex; align-items: center; gap: .6rem;
            padding: .9rem 1rem; flex-shrink: 0;
            box-shadow: 0 2px 6px rgba(0,0,0,.2); }}
    .hdr-title {{ flex: 1; font-size: 1rem; font-weight: 700; min-width: 0;
                  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .hdr-sub {{ font-size: .78rem; opacity: .85; white-space: nowrap; }}
    .back-btn {{ background: rgba(255,255,255,.18); border: none; color: #fff;
                 border-radius: 8px; padding: .4rem .7rem; font-size: .88rem;
                 cursor: pointer; flex-shrink: 0; }}
    .back-btn:active {{ background: rgba(255,255,255,.35); }}

    /* ── List ── */
    #list-scroll {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; }}
    .sec-label {{ font-size: .72rem; font-weight: 700; letter-spacing: .07em;
                  text-transform: uppercase; color: var(--gray);
                  padding: .9rem 1rem .35rem; }}
    .row {{ display: flex; align-items: center; gap: .65rem; background: #fff;
            margin: .3rem .75rem; border-radius: 12px; padding: .85rem 1rem;
            cursor: pointer; box-shadow: 0 1px 4px rgba(0,0,0,.07); }}
    .row:active {{ background: #f7f7f7; }}
    .row.urgent {{ border-left: 4px solid var(--orange-border); }}
    .row-info {{ flex: 1; min-width: 0; }}
    .row-name {{ font-weight: 600; font-size: .92rem;
                 white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .row-loc {{ font-size: .76rem; color: var(--gray); margin-top: .15rem; }}
    .row-dots {{ display: flex; gap: .3rem; flex-shrink: 0; }}
    .dot {{ width: 26px; height: 26px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center; font-size: .8rem; }}
    .dot.check   {{ background: var(--orange-bg); }}
    .dot.due     {{ background: var(--blue-bg); }}
    .dot.ok      {{ background: var(--ok-bg); }}
    .dot.paused  {{ background: var(--gray-bg); }}
    .dot.unknown {{ background: var(--red-bg); }}
    .chevron {{ color: #c8c8c8; font-size: 1rem; flex-shrink: 0; }}

    /* ── Detail ── */
    #detail-scroll {{ flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch;
                      padding: 1rem .75rem 5.5rem; }}
    .d-loc {{ font-size: .82rem; color: var(--gray); margin-bottom: .9rem; }}
    .badge {{ padding: .55rem .8rem; border-radius: 8px; margin: .4rem 0;
              font-size: .875rem; line-height: 1.5; border-left: 4px solid; }}
    .badge.check   {{ background: var(--orange-bg); color: var(--orange); border-color: var(--orange-border); }}
    .badge.due     {{ background: var(--blue-bg);   color: var(--blue);   border-color: var(--blue-border); }}
    .badge.ok      {{ background: var(--ok-bg);     color: var(--ok);     border-color: var(--ok-border); }}
    .badge.paused  {{ background: var(--gray-bg);   color: var(--gray);   border-color: var(--gray-border); }}
    .badge.unknown {{ background: var(--red-bg);    color: var(--red);    border-color: var(--red-border); }}
    .notes {{ margin-top: .85rem; padding: .75rem; background: #fffde7;
              border-radius: 8px; border-left: 3px solid #f9a825; font-size: .8rem; }}
    .notes ul {{ margin-left: 1.1rem; margin-top: .3rem; }}
    .notes li {{ margin: .25rem 0; color: #555; line-height: 1.4; }}

    /* ── Detail nav bar ── */
    .d-nav {{ position: fixed; bottom: 0; left: 0; right: 0; display: flex;
              align-items: center; background: #fff;
              border-top: 1px solid #e0e0e0;
              padding: .7rem 1rem calc(.7rem + env(safe-area-inset-bottom));
              box-shadow: 0 -2px 8px rgba(0,0,0,.07); gap: .75rem; }}
    .nav-btn {{ background: var(--green-bg); border: 1.5px solid #c8e6c9;
                color: var(--green-dk); border-radius: 10px; padding: .55rem 1rem;
                font-size: .9rem; font-weight: 600; cursor: pointer; flex-shrink: 0; }}
    .nav-btn:active {{ background: #dcedc8; }}
    .nav-btn:disabled {{ opacity: .3; pointer-events: none; }}
    .nav-hint {{ flex: 1; font-size: .73rem; color: var(--gray); text-align: center;
                 overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

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
</div>

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
  el.innerHTML = h;
  el.querySelectorAll('.row').forEach(r =>
    r.addEventListener('click', () => openDetail(+r.dataset.i))
  );
}}

function rowHTML(p, i) {{
  const loc = p.location ? `<div class="row-loc">📍 ${{p.location}}</div>` : '';
  return `<div class="row${{p.hasAction ? ' urgent' : ''}}" data-i="${{i}}">
  <div class="row-info">
    <div class="row-name">${{p.name}}</div>${{loc}}
  </div>
  <div class="row-dots">
    <div class="dot ${{p.waterStatus}}">💧</div>
    <div class="dot ${{p.fertStatus}}">🌱</div>
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

  const animClass = dir > 0 ? 'from-right' : dir < 0 ? 'from-left' : '';
  const scr = document.getElementById('detail-scroll');
  scr.innerHTML = `<div class="${{animClass}}">
    ${{p.location ? `<div class="d-loc">📍 ${{p.location}}</div>` : ''}}
    <div class="badge ${{p.waterStatus}}">💧 ${{p.waterMsg}}</div>
    <div class="badge ${{p.fertStatus}}">🌱 ${{p.fertMsg}}</div>
    ${{notesHTML}}
  </div>`;
  scr.scrollTop = 0;
}}

function goTo(i, dir) {{
  if (i < 0 || i >= P.length) return;
  renderDetail(i, dir);
}}

// ── Events ──
document.getElementById('back-btn').addEventListener('click', () => {{
  document.getElementById('detail-view').classList.add('hidden');
  document.getElementById('list-view').classList.remove('hidden');
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
