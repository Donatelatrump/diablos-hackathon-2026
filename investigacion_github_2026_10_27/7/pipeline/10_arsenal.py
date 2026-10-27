"""
10 - Evaluador de arsenal: implementacion de referencia en Python y validacion.

1. Reimplementa en Python, de forma independiente, la logica de lib/arsenal.ts
   (normalizar cada lanzamiento a nivel del mar con su sede de medicion, recta
   principal del arsenal, simulacion suavizada por sede, promedio ponderado por uso)
   y genera tests/arsenal_fixtures.json para verificar la version web.

2. Validacion a nivel pitcher, sin fugas: con modelos entrenados sin cada pitcher
   (5 grupos), su arsenal promedio a nivel del mar se proyecta a altitud extrema
   (1,968 m) y se compara contra lo que realmente paso cuando lanzo alla.
"""
import json, os
import numpy as np
import pandas as pd
import lightgbm as lgb
import simcore
from sklearn.model_selection import GroupKFold

OUT = os.environ.get("OUT", "..")
meta = json.load(open(f"{OUT}/public/data/meta.json")); F = meta["features"]
S = meta["sedes"]; Pm = meta["physics"]["p_magnus_tipo"]; pg = meta["physics"]["p_magnus_global"]
fac = lambda t, r: r ** Pm.get(t, pg)

def recta(pitches):
    fb = sorted([i for i, p in enumerate(pitches) if p["tipo"] in ("Four-Seam", "Sinker")], key=lambda i: -pitches[i]["uso"])
    if fb: return fb[0]
    ct = sorted([i for i, p in enumerate(pitches) if p["tipo"] == "Cutter"], key=lambda i: -pitches[i]["uso"])
    if ct: return ct[0]
    return max(range(len(pitches)), key=lambda i: pitches[i]["RelSpeed"])

def evaluar(booster, scale, a, sedes=("No Altitude", "Medium Altitude", "Harp Helu")):
    """Equivalente a evaluateArsenal() de lib/arsenal.ts (usa el mismo nucleo, simcore)."""
    m = {**meta, "scale": scale}
    tot = sum(max(0, p["uso"]) for p in a["pitches"])
    w = [max(0, p["uso"]) / tot if tot > 0 else 1 / len(a["pitches"]) for p in a["pitches"]]
    mar = []
    for p in a["pitches"]:
        f = fac(p["tipo"], S[p.get("measuredAt", a["measuredAt"])]["rho_ratio"])
        mar.append({**p, "ivb": p["ivb"] / f, "hb_arm": p["hb_arm"] / f})
    i_fb = recta(a["pitches"]); fb = mar[i_fb]
    offs = np.asarray(meta["smoothing"]["offsets"])
    res = {"pitches": [], "stuff": {}}
    for i, p in enumerate(mar):
        q = {**p, "Extension": p.get("Extension", a["Extension"]), "RelHeight": p.get("RelHeight", a["RelHeight"]),
             "rel_side_arm": p.get("rel_side_arm", a["rel_side_arm"]), "isFastball": i == i_fb, "fbTipo": fb["tipo"],
             "fb_relspeed": fb["RelSpeed"], "fb_ivb": fb["ivb"], "fb_hb": fb["hb_arm"], "fb_axis": fb["spin_axis_m"]}
        X = pd.concat([simcore.feature_rows(m, q, s_, offs) for s_ in sedes], ignore_index=True)
        pr = booster.predict(X).reshape(len(sedes), -1).mean(axis=1)
        res["pitches"].append({"tipo": p["tipo"], "stuff": {s_: float(simcore.stuff_plus(m, pr[j], S[s_]["alt"]))
                                                             for j, s_ in enumerate(sedes)}})
    for s_ in sedes:
        res["stuff"][s_] = sum(w[i] * res["pitches"][i]["stuff"][s_] for i in range(len(w)))
    res["recta"] = a["pitches"][i_fb]["tipo"]
    return res

if __name__ == "__main__":
    final = lgb.Booster(model_file="stuff_model.txt")
    D = meta["defaults"]
    def p_(t, uso, **kw): return {"tipo": t, "uso": uso, **{k: D[t][k] for k in ["RelSpeed", "ivb", "hb_arm", "SpinRate", "spin_axis_m"]}, **kw}
    casos = [
        {"mano": "Right", "measuredAt": "No Altitude", "Extension": 6.1, "RelHeight": 5.7, "rel_side_arm": -1.9,
         "pitches": [p_("Four-Seam", 50), p_("Slider", 30), p_("Changeup", 20)]},
        {"mano": "Left", "measuredAt": "Harp Helu", "Extension": 5.8, "RelHeight": 5.9, "rel_side_arm": -1.5,
         "pitches": [p_("Sinker", 40), p_("Cutter", 25), p_("Curveball", 20, measuredAt="No Altitude"), p_("Changeup", 15)]},
        {"mano": "Right", "measuredAt": "Medium Altitude", "Extension": 6.3, "RelHeight": 5.5, "rel_side_arm": -2.1,
         "pitches": [p_("Slider", 60), p_("Curveball", 40)]},   # sin recta: la principal es la mas rapida
    ]
    fx = [{"input": a, "expected": evaluar(final, meta["scale"], a)} for a in casos]
    json.dump(fx, open(f"{OUT}/tests/arsenal_fixtures.json", "w"), indent=1, default=float)
    for c in fx:
        print("caso:", [p["tipo"] for p in c["input"]["pitches"]], "recta:", c["expected"]["recta"],
              {k: round(v, 2) for k, v in c["expected"]["stuff"].items()})

    # ---------------------------------------------------------------- validacion a nivel pitcher
    d = pd.read_parquet("scored.parquet")
    PARAMS = dict(objective="regression", learning_rate=0.03, num_leaves=31, min_child_samples=800,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1, num_threads=2)
    SC = {int(k): v for k, v in meta["scale"].items()}
    MIN_PITCH, MIN_TOTAL = 30, 150
    low = d[d.alt == 0]; ext = d[d.alt == 2]
    nl = low.groupby("pitcher_anon_id").size(); ne = ext.groupby("pitcher_anon_id").size()
    elig = set(nl[nl >= MIN_TOTAL].index) & set(ne[ne >= MIN_TOTAL].index)
    print(f"\nPitchers con >= {MIN_TOTAL} lanzamientos a nivel del mar y en altitud extrema: {len(elig)}")
    out = []
    for k, (tr, te) in enumerate(GroupKFold(5).split(d, groups=d.pitcher_anon_id)):
        m = lgb.train(PARAMS, lgb.Dataset(d.iloc[tr][F], d.iloc[tr].rv), num_boost_round=500)
        test = set(d.iloc[te].pitcher_anon_id) & elig
        for pid in test:
            lp = low[low.pitcher_anon_id == pid]
            g = lp.groupby("tipo").agg(n=("rv", "size"), RelSpeed=("RelSpeed", "mean"), ivb=("ivb", "mean"),
                                       hb_arm=("hb_arm", "mean"), SpinRate=("SpinRate", "mean"), spin_axis_m=("spin_axis_m", "mean"),
                                       Extension=("Extension", "mean"), RelHeight=("RelHeight", "mean"), rel_side_arm=("rel_side_arm", "mean"))
            g = g[(g.n >= MIN_PITCH) & g.index.isin(["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"])]
            if g.empty: continue
            pitches = [{"tipo": t, "uso": float(r.n), **{c: float(r[c]) for c in ["RelSpeed", "ivb", "hb_arm", "SpinRate", "spin_axis_m", "Extension", "RelHeight", "rel_side_arm"]}}
                       for t, r in g.iterrows()]
            a = {"measuredAt": "No Altitude", "Extension": pitches[0]["Extension"], "RelHeight": pitches[0]["RelHeight"],
                 "rel_side_arm": pitches[0]["rel_side_arm"], "pitches": pitches}
            r = evaluar(m, meta["scale"], a, sedes=("No Altitude", "Extreme Altitude"))
            ep = ext[ext.pitcher_anon_id == pid]
            obs = float((100 + 10 * (SC[2]["mean"] - m.predict(ep[F])) / SC[2]["std"]).mean())
            out.append(dict(pitcher=pid, mar=r["stuff"]["No Altitude"], proy=r["stuff"]["Extreme Altitude"], obs=obs,
                            rv_ext=100 * float(ep.rv.mean()), n_ext=len(ep)))
        print(f"  grupo {k+1}/5 listo")
    v = pd.DataFrame(out)
    mae = lambda a, b: float(np.abs(a - b).mean())
    res = {"n_pitchers": int(len(v)),
           "ingenuo": {"corr": float(np.corrcoef(v.mar, v.obs)[0, 1]), "mae": mae(v.mar, v.obs)},
           "proyeccion": {"corr": float(np.corrcoef(v.proy, v.obs)[0, 1]), "mae": mae(v.proy, v.obs)},
           "cambio_corr": float(np.corrcoef(v.proy - v.mar, v.obs - v.mar)[0, 1]),
           "vs_resultado_real": {"ingenuo": float(-np.corrcoef(v.mar, v.rv_ext)[0, 1]),
                                 "proyeccion": float(-np.corrcoef(v.proy, v.rv_ext)[0, 1]),
                                 "techo": float(-np.corrcoef(v.obs, v.rv_ext)[0, 1])}}
    res["reduccion_error_pct"] = 100 * (1 - res["proyeccion"]["mae"] / res["ingenuo"]["mae"])
    rng = np.random.default_rng(0); bs = []
    for _ in range(2000):
        x = v.sample(len(v), replace=True, random_state=int(rng.integers(1e9)))
        bs.append(-np.corrcoef(x.proy, x.rv_ext)[0, 1] + np.corrcoef(x.mar, x.rv_ext)[0, 1])
    res["vs_resultado_real"]["mejora_ic95"] = [float(q) for q in np.percentile(bs, [2.5, 97.5])]
    print(f"\nArsenal completo, {res['n_pitchers']} pitchers no vistos:")
    print(f"  anticipar su Stuff+ de arsenal en altitud: ingenuo corr {res['ingenuo']['corr']:.3f} MAE {res['ingenuo']['mae']:.2f} | "
          f"simulador corr {res['proyeccion']['corr']:.3f} MAE {res['proyeccion']['mae']:.2f} ({res['reduccion_error_pct']:.0f}% menos error)")
    print(f"  predice el cambio: corr {res['cambio_corr']:.3f}")
    vr = res["vs_resultado_real"]
    print(f"  vs carreras reales en altitud: ingenuo {vr['ingenuo']:.3f} | proyeccion {vr['proyeccion']:.3f} | techo {vr['techo']:.3f} | "
          f"mejora IC95 [{vr['mejora_ic95'][0]:+.3f}, {vr['mejora_ic95'][1]:+.3f}]")
    json.dump(res, open(f"{OUT}/public/data/arsenal_validation.json", "w"), indent=1)
