"""Inference for the separate count-transition experiment, never a v9 score."""
import json
from pathlib import Path

from catboost import CatBoostRegressor
import pandas as pd

import entrenar_stuff_plus_v9 as v9


def predict_count_transition(frame, folder=None):
    folder=Path(folder) if folder else Path(__file__).resolve().parents[1]/'precision_count_output_2026_10_28'
    metadata=json.loads((folder/'modelo.json').read_text(encoding='utf-8'))
    path=folder/metadata['model']
    if v9.v6.file_hash(path)!=metadata['model_sha256']:
        raise ValueError('Count-transition model hash mismatch')
    v9.validate_frame(frame)
    prepared=v9.apply_profile(frame,metadata['history'])
    model=CatBoostRegressor().load_model(str(path))
    baseline=v9.baseline_predict(prepared,metadata['baseline'])
    prediction=model.predict(v9.model_features(prepared,metadata['features']))+baseline
    result=v9.postprocess(prediction,baseline,metadata['postprocessor'])
    return pd.DataFrame({'expected_count_transition_proxy':result,'count_reference_proxy':baseline,
                         'experimental':True},index=frame.index)
