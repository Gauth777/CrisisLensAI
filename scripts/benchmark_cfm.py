"""Research-only benchmark: next recorded Tambaram rainfall, NOT flood prediction.

Source date and rainfall fields are used as recorded. Their measurement conventions
remain unverified. This experiment must not power live warnings or NGO dispatch.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import sklearn
import platform

ROOT = Path(__file__).resolve().parents[1]


def examples(frame):
    data = frame.loc[frame.srgid.eq('Tambaram'), ['date', 'rainfall']].copy()
    data['date'] = pd.to_datetime(data.date.str.removesuffix('Z'), errors='coerce', format='mixed')
    if data.date.isna().any() or data.date.duplicated().any():
        raise ValueError('Ambiguous Tambaram dates: resolve before benchmarking')
    data['rainfall'] = pd.to_numeric(data.rainfall, errors='coerce')
    data = data.sort_values('date').set_index('date').asfreq('D')
    # No interpolation and no replacement of missing readings with dry weather.
    data.loc[data.rainfall.lt(0), 'rainfall'] = np.nan
    out = pd.DataFrame(index=data.index)
    for lag in range(7):
        out[f'reading_lag_{lag}'] = data.rainfall.shift(lag)
    out['month_sin'] = np.sin(2 * np.pi * out.index.month / 12)
    out['month_cos'] = np.cos(2 * np.pi * out.index.month / 12)
    out['target'] = data.rainfall.shift(-1)
    out['target_date'] = out.index + pd.Timedelta(days=1)
    return out.dropna().reset_index()


def score(y, pred):
    return {'mae_source_units': float(mean_absolute_error(y, pred)),
            'rmse_source_units': float(np.sqrt(mean_squared_error(y, pred)))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT/'runtime/cfm/chennai-flood-monitor-transactions/data/srg_rain.parquet')
    parser.add_argument('--output', type=Path, default=ROOT/'runtime/cfm/benchmark')
    args = parser.parse_args()
    table = examples(pd.read_parquet(args.data))
    # Partition by target date, not row order; entire future periods are held out.
    train = table[table.target_date.lt('2014-01-01')]
    validation = table[table.target_date.ge('2014-01-01') & table.target_date.lt('2017-01-01')]
    test = table[table.target_date.ge('2017-01-01')]
    if min(len(train), len(validation), len(test)) < 365:
        raise ValueError('Insufficient chronological coverage for this benchmark')
    features = [c for c in table if c.startswith('reading_lag_') or c.startswith('month_')]
    model = RandomForestRegressor(n_estimators=100, max_depth=8, min_samples_leaf=20,
                                  random_state=42, n_jobs=2)
    model.fit(train[features], train.target)
    month_means = train.groupby(train.target_date.dt.month).target.mean()
    result = {'task': 'Predict next recorded Tambaram rainfall value',
        'status': 'research_only_not_validated_for_operations',
        'versions': {'python': platform.python_version(), 'pandas': pd.__version__, 'scikit_learn': sklearn.__version__},
        'source_sha256': hashlib.sha256(args.data.read_bytes()).hexdigest(),
        'features': features, 'splits': {}, 'metrics': {},
        'flood_prediction_accuracy': None,
        'limitations': ['No flood or assistance-demand target.',
          'Source rainfall units, accumulation interval and date conventions not independently validated.',
          'Historical station-name match is not proof of present locality coverage.',
          'No tuning on validation or test; fixed experimental parameters.',
          'Never deploy this research model for warnings or recommendations.']}
    for name, split in [('train', train), ('validation', validation), ('test', test)]:
        result['splits'][name] = {'rows': len(split), 'target_start': str(split.target_date.min().date()),
                                  'target_end': str(split.target_date.max().date())}
        if name == 'train':
            continue
        predictions = {'persistence': split.reading_lag_0.to_numpy(),
            'training_month_mean': split.target_date.dt.month.map(month_means).fillna(train.target.mean()).to_numpy(),
            'random_forest': model.predict(split[features])}
        result['metrics'][name] = {k: score(split.target, v) for k, v in predictions.items()}
        args.output.mkdir(parents=True, exist_ok=True)
        export = split[['date','target_date','target']].copy()
        for k, v in predictions.items():
            export[k] = v
        export.to_csv(args.output / f'{name}_predictions.csv', index=False)
    result['promotion_allowed'] = False
    args.output.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': model, 'features': features, 'research_only': True}, args.output/'research_rainfall.joblib')
    (args.output/'metrics.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    table.to_csv(args.output/'tambaram_examples.csv', index=False)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
