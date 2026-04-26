"""
wlasc_survey.py — Survey unique WLASC strings from ~500 real Poznań parcels.

Imports geopoz_client and parcel_analyzer directly (no server needed).
Outputs wlasc_survey_results.md with a full table + summary.

Usage:
    python wlasc_survey.py
"""

import itertools
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, '.')

import geopoz_client as gc
from parcel_analyzer import analyze_parcel

TARGET = 500
MAX_WORKERS = 8
BATCH_SIZE = 80

# Poznań bounding box grid (step ~330 m)
lats = [round(52.31 + i * 0.003, 5) for i in range(68)]
lons = [round(16.74 + j * 0.003, 5) for j in range(121)]
coords = list(itertools.product(lats, lons))

print(f"Grid: {len(coords)} coordinate points → targeting {TARGET} unique parcels")

meta = gc.get_powierzenia_meta()
seen_ozn: set[str] = set()
records: list[dict] = []
lock = threading.Lock()
stop_event = threading.Event()


def query_one(lat: float, lon: float) -> gc.ParcelAttributes | None:
    if stop_event.is_set():
        return None
    attrs, err = gc.get_parcel_info(lat, lon)
    if err or attrs is None:
        return None
    return attrs


coord_iter = iter(coords)
done = False

while not done:
    batch = list(itertools.islice(coord_iter, BATCH_SIZE))
    if not batch:
        print("Exhausted grid without reaching target — add denser sub-grid.")
        break

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(query_one, lat, lon) for lat, lon in batch]
        for f in as_completed(futures):
            attrs = f.result()
            if attrs is None:
                continue
            with lock:
                if attrs.ozn_dz in seen_ozn:
                    continue
                if stop_event.is_set():
                    continue
                seen_ozn.add(attrs.ozn_dz)
                pow_entries = gc.get_powierzenia(attrs.ozn_dz)
                scenario = analyze_parcel(attrs, pow_entries, meta)
                records.append({
                    'ozn_dz': attrs.ozn_dz,
                    'wlasc': attrs.wlasc,
                    'wlad': attrs.wlad,
                    'klasouzytki': attrs.klasouzytki,
                    'scenario_type': scenario.type.value,
                    'manager_label': scenario.manager_label,
                    'manager_name': scenario.manager_name or '—',
                    'contextual_note': scenario.contextual_note or '—',
                    'show_wlasc': scenario.show_wlasc,
                    'confidence': scenario.confidence,
                })
                count = len(seen_ozn)
                if count % 50 == 0:
                    print(f"  {count} parcels collected…")
                if count >= TARGET:
                    stop_event.set()
                    done = True
                    break

print(f"\nTotal unique parcels queried: {len(records)}")

# --- Build deduplicated-by-WLASC table ---
# For each unique (wlasc, scenario_type) key, keep one sample record
wlasc_map: dict[tuple[str, str], dict] = {}
wlasc_count: dict[tuple[str, str], int] = defaultdict(int)

for r in records:
    key = (r['wlasc'], r['scenario_type'])
    wlasc_count[key] += 1
    if key not in wlasc_map:
        wlasc_map[key] = r

rows = sorted(wlasc_map.values(), key=lambda r: (r['scenario_type'], r['wlasc']))

# --- Scenario type counts ---
scenario_counts: dict[str, int] = defaultdict(int)
for r in records:
    scenario_counts[r['scenario_type']] += 1

# --- Write Markdown output ---
SCENARIO_ORDER = [
    'xlsx_multi', 'xlsx_single',
    'zdm_city', 'zdm_other',
    'church',
    'skarb_uw', 'skarb_zasob', 'skarb_tz', 'skarb_other',
    'gminna_entity',
    'private',
    'city_mixed', 'city_zasob', 'city_uw', 'city_tz',
    'unknown',
]

md_lines = [
    "# WLASC Survey Results",
    "",
    f"Parcels queried: **{len(records)}**  |  Unique WLASC×Scenario combos: **{len(wlasc_map)}**",
    "",
    "## Summary — parcels per scenario",
    "",
    "| Scenario | Count |",
    "|----------|-------|",
]
for s in SCENARIO_ORDER:
    c = scenario_counts.get(s, 0)
    if c:
        md_lines.append(f"| `{s}` | {c} |")
md_lines.extend(["", "---", ""])

md_lines += [
    "## Full table — unique WLASC strings",
    "",
    "Columns: raw WLASC from EGIB → which scenario branch fires → what #panel shows",
    "",
    "| # | WLASC (d.wlasc) | Scenario | Manager label | Manager name | Contextual note | show_wlasc | Confidence | Sample parcel |",
    "|---|-----------------|----------|--------------|--------------|-----------------|-----------|------------|---------------|",
]

def esc(s: str) -> str:
    return s.replace('|', '\\|').replace('\n', ' ')

for i, r in enumerate(rows, 1):
    key = (r['wlasc'], r['scenario_type'])
    cnt = wlasc_count[key]
    wlasc_cell = f"`{esc(r['wlasc'])}`" if r['wlasc'] else "*(empty)*"
    md_lines.append(
        f"| {i} | {wlasc_cell} | `{r['scenario_type']}` | {esc(r['manager_label'])} "
        f"| {esc(r['manager_name'])} | {esc(r['contextual_note'])} "
        f"| {'✓' if r['show_wlasc'] else '✗'} | {r['confidence']} | `{r['ozn_dz']}` |"
    )

output_path = 'wlasc_survey_results.md'
with open(output_path, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(md_lines) + '\n')

print(f"Results written to {output_path}")
print(f"Unique WLASC×Scenario combinations: {len(wlasc_map)}")
print("\nScenario breakdown:")
for s in SCENARIO_ORDER:
    c = scenario_counts.get(s, 0)
    if c:
        print(f"  {s:20s} {c:4d} parcels")
