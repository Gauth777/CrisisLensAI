"""Download pinned CFM-DSS mirrors and audit them without changing the live app."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def download(item):
    url, path = item
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=90) as response:
                    body = response.read()
                temp = path.with_suffix(path.suffix + '.part')
                temp.write_bytes(body)
                temp.replace(path)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
    return {'url': url, 'file': str(path), 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def profile(path):
    import pandas as pd
    import pyarrow.parquet as pq
    df = pd.read_parquet(path)
    result = {'file': str(path), 'rows': len(df), 'columns': {}, 'date_coverage': {},
              'area_text_matches': {}, 'numeric_summary': {}}
    for col in df.columns:
        s = df[col]
        result['columns'][col] = {'dtype': str(s.dtype), 'missing': int(s.isna().sum())}
        if any(k in col.lower() for k in ('date', 'timestamp')) and len(df):
            # Date-only fields sometimes carry a literal trailing Z, not an ISO time.
            raw = s.astype('string').str.replace(r'^(\d{4}-\d{2}-\d{2})Z$', r'\1', regex=True)
            parsed = pd.to_datetime(raw, errors='coerce', utc=True, format='mixed')
            result['date_coverage'][col] = {'parsed': int(parsed.notna().sum()),
                'min': str(parsed.min()), 'max': str(parsed.max()),
                'by_year': {str(k): int(v) for k, v in parsed.dt.year.value_counts().sort_index().items()}}
        if any(k in col.lower() for k in ('rainfall', 'waterlevel', 'water_level')):
            num = pd.to_numeric(s, errors='coerce')
            result['numeric_summary'][col] = {'numeric': int(num.notna().sum()),
                'zero': int(num.eq(0).sum()), 'negative': int(num.lt(0).sum()),
                'min': float(num.min()) if num.notna().any() else None,
                'max': float(num.max()) if num.notna().any() else None}
    textcols = [c for c in df.columns if df[c].dtype == 'object' and c != 'geometry']
    for area, pattern in {'Velachery': 'velach', 'Tambaram': 'tambaram',
                           'Chromepet': 'chrom[ep]*et|chrompet'}.items():
        mask = pd.Series(False, index=df.index)
        matched_columns = []
        for c in textcols:
            match = df[c].astype('string').str.contains(pattern, case=False, na=False, regex=True)
            if match.any():
                mask |= match
                matched_columns.append(c)
        result['area_text_matches'][area] = {'rows': int(mask.sum()), 'columns': matched_columns}
    keys = {'srg_rain.parquet': ('srgid', 'time_of_measurement'),
            'aws_arg_rain_met.parquet': ('awsid', 'time_of_measurement'),
            'awlr_waterlevel.parquet': ('awlrid', 'time_of_measurementtemp')}
    if path.name in keys:
        station, clock = keys[path.name]
        result['station_count'] = int(df[station].nunique())
        result['duplicate_station_date_time'] = int(df.duplicated([station, 'date', clock]).sum())
    if path.name == 'awlr_waterlevel.parquet':
        date = pd.to_datetime(df.date.str.removesuffix('Z'), errors='coerce', utc=True, format='mixed')
        combined = pd.to_datetime(df.combined_datetime, errors='coerce', utc=True, format='mixed')
        offsets = (combined.dt.normalize() - date.dt.normalize()).dt.days
        result['combined_vs_date_day_offsets'] = {str(k): int(v) for k, v in offsets.value_counts(dropna=False).items()}
    metadata = pq.read_schema(path).metadata or {}
    if b'geo' in metadata:
        geo = json.loads(metadata[b'geo'])
        result['geo_metadata'] = geo
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'runtime/cfm')
    parser.add_argument('--offline', action='store_true', help='Audit already downloaded files only')
    args = parser.parse_args()
    sources = json.loads((ROOT / 'docs/data/cfm_sources.json').read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = []
    for name, source in sources.items():
        for f in source['files']:
            jobs.append((f"https://huggingface.co/datasets/{source['repository']}/resolve/{source['revision']}/{f}", args.output / name / f))
    inventory, errors = [], []
    if args.offline:
        for url, path in jobs:
            if path.exists():
                inventory.append(download((url, path)))
            else:
                errors.append({'file': str(path), 'error': 'missing_offline'})
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [(job, pool.submit(download, job)) for job in jobs]
            for job, future in futures:
                try:
                    entry = future.result()
                    inventory.append(entry)
                    print('Downloaded', job[1].name, flush=True)
                except Exception as exc:
                    errors.append({'file': str(job[1]), 'error': str(exc)})
    profiles = []
    for entry in inventory:
        if entry['file'].endswith('.parquet'):
            try:
                profiles.append(profile(Path(entry['file'])))
                print('Audited', Path(entry['file']).name, flush=True)
            except Exception as exc:
                errors.append({'file': entry['file'], 'error': str(exc)})
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'sources': sources,
        'inventory': inventory, 'profiles': profiles, 'errors': errors,
        'limitations': ['Third-party historical mirrors; not live feeds.',
          'Text matches do not establish geographical coverage or station joins.',
          'Water-level datum and rainfall accumulation interval require source validation.',
          'Null is unknown, not zero. No flood labels or NGO demand are inferred.',
          'Original publisher reuse terms remain to be established.']}
    (args.output / 'audit.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    summary = {'generated_at': report['generated_at'], 'sources': sources,
        'downloaded_files': len(inventory), 'table_count': len(profiles), 'errors': errors,
        'files': [{**e, 'file': str(Path(e['file']).relative_to(args.output))} for e in inventory],
        'tables': [{k: (str(Path(v).relative_to(args.output)) if k == 'file' else v)
                   for k, v in p.items() if k not in ('columns', 'geo_metadata')} for p in profiles],
        'limitations': report['limitations']}
    (args.output / 'findings.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(f"{len(profiles)} tables audited; {len(errors)} errors. Report: {args.output / 'audit.json'}")
    if errors:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
