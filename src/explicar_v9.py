"""Additive SHAP explanations in the exact units of the physical Stuff+ score."""
import numpy as np
import pandas as pd
from catboost import Pool

import entrenar_stuff_plus_v9 as v9


def explain_physical(frame, bundle):
    v9.validate_frame(frame)
    meta, models = bundle
    task = meta["tasks"]["stuff_run_value"]
    reference = meta["reference"]["stuff_plus"]
    columns = task["features"]
    if not reference["informative"] or task["postprocessor"]["method"] == "baseline":
        return {"base": np.full(len(frame), 100.), "contributions": pd.DataFrame(0., index=range(len(frame)), columns=columns),
                "score": np.full(len(frame), 100.), "informative": False}
    prepared = v9.apply_profile(frame, meta["profile"])
    pool = Pool(v9.v6.features(prepared, columns), cat_features=[c for c in columns if c in v9.v5.CATEGORICAL])
    shap = models["stuff_run_value"].get_feature_importance(pool, type="ShapValues", thread_count=2)
    weight = task["postprocessor"].get("weight", 1.)
    factor = -10*weight/reference["std"]
    contributions = pd.DataFrame(shap[:, :-1]*factor, columns=columns)
    base = 100+10*(-task["baseline"]["prior"]-weight*shap[:, -1]-reference["mean"])/reference["std"]
    return {"base": base, "contributions": contributions, "score": base+contributions.sum(axis=1).to_numpy(), "informative": True}
