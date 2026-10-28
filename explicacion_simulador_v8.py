"""SHAP local del Stuff+ físico heredado, comprobado contra el score mostrado."""
import numpy as np
import pandas as pd
from catboost import Pool
import entrenar_stuff_plus_v5 as v5


def explain_stuff(row, bundle, expected_score, reference_id):
    meta8, _, parent7 = bundle
    meta7, _, parent6 = parent7
    meta6, base_bundle, _ = parent6
    if meta7["stack"]["chosen"]["promoted"] or meta6["tasks"]["stuff_run_value"]["chosen"]["weight"]:
        raise ValueError("La explicación disponible requiere el modelo físico heredado sin mezcla adicional.")
    if meta8["selection"].get("stuff_run_value", {}).get("promoted", False):
        raise ValueError("La explicación disponible no cubre un modelo físico v8 nuevo.")
    metadata, models = base_bundle
    reference = metadata["reference"]["stuff_plus"] if reference_id == "v5_fallback" else meta6["reference"]["stuff_plus"]
    task = metadata["tasks"]["stuff_run_value"]
    prepared = v5.apply_profile(pd.DataFrame([row]), metadata["profile"])
    features = v5.features(prepared, task["features"])
    pool = Pool(features, cat_features=[c for c in task["features"] if c in v5.CATEGORICAL])
    values = models["stuff_run_value"].get_feature_importance(pool, type="ShapValues", thread_count=2)[0]
    contributions = -10 * task["alpha"] * values[:-1] / reference["std"]
    base = 100 + 10 * (-(task["alpha"] * values[-1] + (1-task["alpha"])*task["prior"]) - reference["mean"]) / reference["std"]
    if not np.isclose(base + contributions.sum(), expected_score, atol=1e-6, rtol=0):
        raise ValueError("La explicación no reconstruye el score mostrado; se omite para evitar una atribución incorrecta.")
    return float(base), pd.DataFrame({"Variable": task["features"], "Aporte a Stuff+ (puntos)": contributions})
