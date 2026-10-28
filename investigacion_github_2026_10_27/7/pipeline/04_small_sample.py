"""04 - ¿Con cuantos lanzamientos Stuff+ ya dice algo? Muestra chica vs. resultado real."""
import numpy as np, pandas as pd, json
d = pd.read_parquet("scored.parquet")
rng = np.random.default_rng(3)
g = d.groupby(["pitcher_anon_id", "AutoPitchType", "year"])
rows = []
for N in [25, 50, 100, 200]:
    S, R, Y = [], [], []
    for _, x in g:
        if len(x) < N + 150: continue
        idx = rng.permutation(len(x)); a, b = x.iloc[idx[:N]], x.iloc[idx[N:]]
        S.append(a.stuff_plus.mean()); R.append(a.rv.mean()); Y.append(b.rv.mean())
    S, R, Y = map(np.array, (S, R, Y))
    rows.append(dict(N=N, n=len(S), stuff=-np.corrcoef(S, Y)[0, 1], rv=np.corrcoef(R, Y)[0, 1]))
    print(f"  con {N:3d} lanzamientos (n={len(S)}): Stuff+ predice el resto {rows[-1]['stuff']:.2f} | RV real {rows[-1]['rv']:.2f}")
m = json.load(open("model_meta.json")); m["small_sample"] = rows; json.dump(m, open("model_meta.json", "w"), indent=2, default=float)
print("\nDistribución:")
pt = d.groupby(["pitcher_anon_id","year"]).filter(lambda x: len(x) >= 300).groupby(["pitcher_anon_id","year"]).stuff_plus.mean()
print("  pitcher-temporada (>=300 lanz.): p5 %.1f  p25 %.1f  p50 %.1f  p75 %.1f  p95 %.1f  sd %.1f" % (*pt.quantile([.05,.25,.5,.75,.95]), pt.std()))
print("\nStuff+ medio por tipo (etiqueta Trackman, solo informativo):")
print(d.groupby("AutoPitchType").stuff_plus.agg(["mean","size"]).query("size>1000").round(1).sort_values("mean").to_string())
