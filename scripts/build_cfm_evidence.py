"""Build research station candidates, event joins, and a self-contained coverage map.

No API/model calls. Registry proximity is not catchment coverage or live availability.
"""
from __future__ import annotations
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
# Same representative locality centres as crisislens/data/environment.py, not incident points.
AREAS = {'Tambaram': (12.9300, 80.1100), 'Chromepet': (12.9516, 80.1401),
         'Velachery': (12.9807, 80.2189)}
REGISTRIES = [
 ('srg_pwd_existing_53', 'stationname', 'SRG', 'srg_rain', 'srgid'),
 ('aws_registry_39', 'awsid', 'AWS', 'aws_arg_rain_met', 'awsid'),
 ('awlr_44', 'awlrid', 'AWLR', 'awlr_waterlevel', 'awlrid'),
 ('awlr_stations_121', 'location', 'AWLR registry only', None, None)]


def distance(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    v = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(v)))


def clean_date(series):
    return pd.to_datetime(series.astype('string').str.removesuffix('Z'), errors='coerce', format='mixed', utc=True)


def build(data):
    stations, registries, hashes = [], [], {}
    for registry, key, family, transaction, transaction_key in REGISTRIES:
        path = data/'stations'/f'{registry}.parquet'
        hashes[str(path.relative_to(data))] = hashlib.sha256(path.read_bytes()).hexdigest()
        table = pd.read_parquet(path)
        counts, spans = {}, {}
        if transaction:
            tp = data/'data'/f'{transaction}.parquet'
            hashes[str(tp.relative_to(data))] = hashlib.sha256(tp.read_bytes()).hexdigest()
            readings = pd.read_parquet(tp)
            readings['_day'] = clean_date(readings.date)
            counts = readings.groupby(transaction_key).size().to_dict()
            for name, group in readings.groupby(transaction_key):
                valid = group._day.dropna()
                spans[name] = {'first': str(valid.min().date()) if len(valid) else None,
                               'last': str(valid.max().date()) if len(valid) else None}
        ambiguous = set(table.loc[table[key].duplicated(keep=False), key].dropna())
        accepted, matched, invalid_coordinates = 0, 0, 0
        for _, row in table.iterrows():
            name = str(row[key]) if pd.notna(row[key]) else None
            try:
                lat, lon = float(row.latitude), float(row.longitude)
            except (ValueError, TypeError):
                invalid_coordinates += 1
                continue
            # Study-region sanity check; never silently swap axes or repair invalid points.
            if not (12 <= lat <= 14 and 79 <= lon <= 81):
                invalid_coordinates += 1
                continue
            accepted += 1
            n = int(counts.get(name, 0)) if name not in ambiguous else 0
            matched += int(n > 0)
            near = {a: round(distance(point, (lat, lon)), 3) for a, point in AREAS.items()}
            stations.append({'id': f'{registry}:{row["id"]}', 'name': name or 'Missing registry name',
                'family': family, 'registry': registry, 'latitude': lat, 'longitude': lon,
                'match_status': 'ambiguous_registry_key' if name in ambiguous else 'exact_key_historical_candidate' if n else 'registry_only_no_exact_series_match',
                'historical_rows': n, 'record_dates': spans.get(name) if n else None,
                'live_status': 'not_verified', 'catchment_link': 'not_verified',
                'distances_km': near})
        registries.append({'registry': registry, 'rows': len(table), 'valid_coordinates': accepted,
                           'invalid_coordinates': invalid_coordinates, 'exact_key_candidates': matched})
    selected = {}
    for area in AREAS:
        selected[area] = {}
        for family in ['SRG','AWS','AWLR','AWLR registry only']:
            selected[area][family] = sorted([s for s in stations if s['family']==family],
                key=lambda s: s['distances_km'][area])[:3]
    return {'as_of': '2026-10-30', 'area_centres': AREAS, 'registries': registries,
        'input_sha256': hashes, 'nearest_candidates': selected,
        'map_stations': [s for s in stations if min(s['distances_km'].values()) <= 15],
        'map_radius_km': 15, 'coverage_verified': False,
        'limitations': ['Distances are from representative locality centres, not affected streets.',
         'A 15 km display filter is not a sensor coverage boundary.',
         'Exact identifier matches are candidates; identity history and catchment links need review.',
         'Registry-only points can duplicate matched sensors; do not sum them as unique sensors.',
         'Proposed station tables are excluded. No reporting sensor has been verified live.']}


def validate_cases(catalogue):
    ids = {s['id'] for s in catalogue['sources']}
    seen = set()
    for row in catalogue['incidents']:
        if row['id'] in seen or row['area'] not in AREAS:
            raise ValueError('Duplicate case or unsupported locality')
        seen.add(row['id'])
        if not row['source_ids'] or not set(row['source_ids']) <= ids:
            raise ValueError('Case lacks valid evidence references')
        date.fromisoformat(row['observed_on'])
        if row['training_eligible'] or row['flood_label'] is not None:
            raise ValueError('Seed cases require human adjudication before supervised training')
        for conflict in row['conflicts']:
            if not {a['source_id'] for a in conflict['accounts']} <= set(row['source_ids']):
                raise ValueError('Conflict cites evidence outside case')


def event_joins(catalogue, data):
    """Availability check only. Anchor is report observation date, NOT flood onset."""
    frame = pd.read_parquet(data/'data/srg_rain.parquet')
    frame['_day'] = clean_date(frame.date)
    rows = []
    for event in catalogue['incidents']:
        # Only the audited exact locality-name series; no guessed nearest-series proxy.
        series = frame.loc[frame.srgid.eq(event['area'])]
        anchor = pd.Timestamp(event['observed_on'], tz='UTC')
        window = series[series._day.ge(anchor-pd.Timedelta(days=7)) & series._day.lt(anchor)]
        valid = window.rainfall.notna() & window.rainfall.ge(0)
        rows.append({'incident_id': event['id'], 'event_group': event['event_group'],
            'anchor': event['observed_on'], 'anchor_kind': 'reported_observation_day_not_onset',
            'window': 'preceding_7_calendar_days_excluding_anchor',
            'exact_locality_series_rows': len(series), 'window_rows': len(window),
            'window_nonnegative_nonmissing_readings': int(valid.sum()),
            'distinct_recorded_days': int(window._day.nunique()),
            'predictive_join_allowed': False,
            'reason': 'Onset, measurement intervals and station-to-site relationship remain unverified.'})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT/'runtime/cfm/chennai-flood-monitor-transactions')
    parser.add_argument('--output', type=Path, default=ROOT/'research/cfm/generated')
    args = parser.parse_args()
    catalogue = json.loads((ROOT/'research/cfm/incidents.json').read_text())
    validate_cases(catalogue)
    coverage = build(args.data)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'station_coverage.json').write_text(json.dumps(coverage, indent=2, allow_nan=False)+'\n')
    joins = event_joins(catalogue, args.data)
    (args.output/'incident_join_audit.json').write_text(json.dumps(joins, indent=2)+'\n')
    review = pd.DataFrame([{'incident_id': e['id'], 'event_group':e['event_group'],
        'area':e['area'], 'reported_observation_day':e['observed_on'],
        'evidence_status':e['occurrence_status'], 'unresolved_conflicts':len(e['conflicts']),
        'reviewer':'', 'reviewed_on':'', 'confirmed_onset':'', 'confirmed_end':'',
        'adjudication':'', 'evidence_notes':''} for e in catalogue['incidents']])
    # Blank review templates only; preserve a reviewer's completed work on rerun.
    review_path = args.output/'human_review_template.csv'
    if not review_path.exists():
        review.to_csv(review_path,index=False)
    payload = json.dumps({'coverage':coverage,'catalogue':catalogue},allow_nan=False).replace('<','\\u003c')
    html = (ROOT/'research/cfm/map_template.html').read_text().replace('__PAYLOAD__',payload)
    (args.output/'coverage_map.html').write_text(html)
    print(json.dumps({'registry_counts':coverage['registries'], 'map_points':len(coverage['map_stations']),
        'cases':len(catalogue['incidents']), 'event_groups':len({e['event_group'] for e in catalogue['incidents']}),
        'negative_examples':len(catalogue['negative_examples']), 'joins':joins},indent=2))

if __name__ == '__main__':
    main()
