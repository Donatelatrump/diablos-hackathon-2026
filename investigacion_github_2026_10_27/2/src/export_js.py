"""Exporta boosters LightGBM a arreglos compactos para evaluación en el navegador y verifica contra Python."""
import json, numpy as np, lightgbm as lgb, pandas as pd, subprocess, os
OUT = '/home/claude/stuffplus/out'


def compact(booster, ndig=7):
    d = booster.dump_model()
    trees = []
    for t in d['tree_info']:
        F, T, L, R, V, D = [], [], [], [], [], []
        def walk(n):
            i = len(F)
            if 'leaf_value' in n:
                F.append(-1); T.append(0); L.append(-1); R.append(-1); V.append(round(n['leaf_value'], 7)); D.append(0)
                return i
            F.append(n['split_feature']); T.append(round(n['threshold'], ndig)); L.append(0); R.append(0); V.append(0); D.append(1 if n['default_left'] else 0)
            L[i] = walk(n['left_child']); R[i] = walk(n['right_child'])
            return i
        walk(t['tree_structure'])
        trees.append([F, T, L, R, V, D])
    return dict(features=d['feature_names'], objective=d['objective'], trees=trees)


JS = r"""
function lgbPredict(model, x){ // x: object feature->value
  const feats = model.features; let s = 0;
  for (const tr of model.trees){
    const [F,T,L,R,V,D] = tr; let i = 0;
    while (F[i] !== -1){
      const v = x[feats[F[i]]];
      if (v === undefined || v === null || Number.isNaN(v)) i = D[i] ? L[i] : R[i];
      else i = (v <= T[i]) ? L[i] : R[i];
    }
    s += V[i];
  }
  if (model.objective.startsWith('binary')) return 1/(1+Math.exp(-s));
  return s;
}
"""

if __name__ == '__main__':
    models = {}
    for name in ['stuff_rv', 'stuff_whiff', 'stuff_gb', 'stuff_hard', 'stuff_hr', 'stuff_called_strike', 'stuff_chase']:
        p = f'{OUT}/models/{name}.txt'
        if not os.path.exists(p): continue
        b = lgb.Booster(model_file=p)
        models[name] = compact(b)
    json.dump(models, open(f'{OUT}/models/compact_models.json', 'w'), separators=(',', ':'))
    print('size MB', round(os.path.getsize(f'{OUT}/models/compact_models.json') / 1e6, 2))
    # verificación con node
    df = pd.read_parquet('/home/claude/stuffplus/data/pitches_targets.parquet').sample(300, random_state=3)
    fs = json.load(open(f'{OUT}/feature_sets.json'))
    X = df[fs['STUFF']]
    py = {n: lgb.Booster(model_file=f'{OUT}/models/{n}.txt').predict(X).tolist() for n in models}
    json.dump(dict(rows=X.to_dict(orient='records'), py=py), open('/tmp/claude-0/-home-claude/445ecc6a-7282-5a09-9306-3e209ffb5f6c/scratchpad/verify.json', 'w'))
    open('/tmp/claude-0/-home-claude/445ecc6a-7282-5a09-9306-3e209ffb5f6c/scratchpad/verify.js', 'w').write(JS + r"""
const fs=require('fs'); const M=JSON.parse(fs.readFileSync('/home/claude/stuffplus/out/models/compact_models.json'));
const V=JSON.parse(fs.readFileSync('/tmp/claude-0/-home-claude/445ecc6a-7282-5a09-9306-3e209ffb5f6c/scratchpad/verify.json'));
for (const n of Object.keys(M)){ let maxd=0; V.rows.forEach((r,i)=>{ const p=lgbPredict(M[n], r); maxd=Math.max(maxd, Math.abs(p-V.py[n][i])); }); console.log(n, 'max abs diff', maxd.toExponential(2)); }
""")
    print(subprocess.run(['node', '/tmp/claude-0/-home-claude/445ecc6a-7282-5a09-9306-3e209ffb5f6c/scratchpad/verify.js'], capture_output=True, text=True).stdout)
