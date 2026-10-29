"""Optional, gated conditional-whiff overlay; frozen v9 remains the fallback."""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

import entrenar_stuff_plus_v9 as v9
from precision_features import FLIGHT, SEQUENCE, RECENT, FORBIDDEN

OUTPUT = Path(__file__).resolve().parent / 'precision_output_2026_10_28'


def model_features(frame, columns):
    if FORBIDDEN.intersection(columns):
        raise ValueError('Outcome or identifier in precision predictors')
    rows = frame.copy()
    for col in columns:
        if col not in rows and col in FLIGHT + SEQUENCE + RECENT:
            rows[col] = np.nan
    return v9.model_features(rows, columns)


def load_precision(folder=OUTPUT, require_accepted=True):
    folder = Path(folder)
    path = folder / 'precision.json'
    if not path.exists():
        return None
    try:
        meta = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None  # A training process may still be writing a non-active report.
    if require_accepted and not meta.get('accepted'):
        return None
    if 'model' not in meta:
        return None
    model_path = folder / meta['model']
    if v9.v6.file_hash(model_path) != meta['model_sha256']:
        raise ValueError('Precision model hash mismatch')
    model = CatBoostClassifier().load_model(str(model_path))
    return meta, model


def eligible_inputs(frame, meta):
    valid = pd.Series(True, index=frame.index)
    required = meta['required_inputs']
    for key in required:
        if key not in frame:
            return pd.Series(False, index=frame.index)
        value = pd.to_numeric(frame[key], errors='coerce')
        valid &= np.isfinite(value)
        if key in meta.get('bounds', {}):
            low, high = meta['bounds'][key]
            valid &= value.between(low, high)
    if 'ZoneSpeed' in required:
        valid &= pd.to_numeric(frame.ZoneSpeed, errors='coerce').le(pd.to_numeric(frame.RelSpeed, errors='coerce'))
    for flag, fields in [('previous_available', ['previous_velocity','previous_hb','previous_ivb','velocity_change','hb_change','ivb_change']),
                         ('recent_available', ['recent_velocity','recent_hb','recent_ivb','recent_pitches'])]:
        if flag in required:
            status=pd.to_numeric(frame[flag],errors='coerce')
            valid &= status.isin([0.,1.])
            complete=pd.Series(True,index=frame.index)
            for col in fields:
                complete &= np.isfinite(pd.to_numeric(frame[col],errors='coerce')) if col in frame else False
            valid &= status.eq(0) | complete
    if 'recent_available' in required:
        count=pd.to_numeric(frame.get('recent_pitches',pd.Series(np.nan,index=frame.index)),errors='coerce')
        valid &= frame.recent_available.eq(0) | count.ge(10)
    return valid


def apply_precision(frame, result, bundle, precision):
    result = result.copy()
    result['precision_whiff_available'] = False
    if precision is None:
        return result
    meta, model = precision
    if meta['base_bundle_sha256'] != bundle[0].get('precision_base_bundle_sha256'):
        # The caller binds the frozen bundle hash; never mix model generations.
        return result
    valid = eligible_inputs(frame.reset_index(drop=True), meta)
    if not valid.any():
        return result
    prepared = v9.apply_profile(frame.reset_index(drop=True).loc[valid], bundle[0]['profile'])
    raw = model.predict_proba(model_features(prepared, meta['features']))[:, 1]
    baseline = v9.baseline_predict(prepared, meta['baseline'])
    probability = v9.postprocess(raw, baseline, meta['postprocessor'])
    result.loc[valid, 'p_whiff_given_swing'] = probability
    result.loc[valid, 'precision_whiff_available'] = True
    return result


def infer(frame, bundle, precision=None):
    return apply_precision(frame, v9.infer(frame, bundle), bundle, precision)


@lru_cache(maxsize=4)
def _cached_precision(folder, modified):
    return load_precision(folder)


def infer_dashboard(frame, bundle, output):
    path = OUTPUT / 'precision.json'
    precision = _cached_precision(str(OUTPUT), path.stat().st_mtime_ns) if path.exists() else None
    metadata = {**bundle[0], 'precision_base_bundle_sha256': v9.v6.file_hash(Path(output)/'bundle.json')}
    return infer(frame, (metadata,bundle[1]), precision)


@lru_cache(maxsize=4)
def _cached_candidate(folder, modified):
    return load_precision(folder, require_accepted=False)


def preview_dashboard(frame, result, bundle, output):
    """Explicit comparison only; never changes the caller's main predictions."""
    path=OUTPUT/'precision.json'
    candidate=_cached_candidate(str(OUTPUT),path.stat().st_mtime_ns) if path.exists() else None
    metadata={**bundle[0],'precision_base_bundle_sha256':v9.v6.file_hash(Path(output)/'bundle.json')}
    return apply_precision(frame,result,(metadata,bundle[1]),candidate)
