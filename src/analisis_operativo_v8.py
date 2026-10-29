"""Agregados de entrega, asociaciones ajustadas de entorno y casos de scouting."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import entrenar_stuff_plus_v8 as v8
v5,v6=v8.v5,v8.v6
OUT=Path("entrega_v8")


def paired_environment(frame,outcome,comparison,min_cell=3):
    keys=["pitcher_anon_id","year","AutoPitchType","BatterSide","Balls","Strikes"]
    rows=frame.loc[frame.altitude_category.isin(["No Altitude",comparison])].dropna(subset=keys+[outcome])
    agg=rows.groupby(keys+["altitude_category"])[outcome].agg(["mean","size"]).reset_index()
    a=agg.loc[agg.altitude_category.eq("No Altitude")].drop(columns="altitude_category")
    b=agg.loc[agg.altitude_category.eq(comparison)].drop(columns="altitude_category")
    pairs=a.merge(b,on=keys,suffixes=("_low","_high"),validate="one_to_one")
    pairs=pairs.loc[(pairs.size_low>=min_cell)&(pairs.size_high>=min_cell)].copy()
    if pairs.empty: return None
    pairs["weight"]=np.minimum(pairs.size_low,pairs.size_high)
    pairs["weighted_delta"]=(pairs.mean_high-pairs.mean_low)*pairs.weight
    clusters=pairs.groupby("pitcher_anon_id")[["weighted_delta","weight"]].sum().to_numpy()
    if len(clusters)<5: return None
    rng=np.random.default_rng(910)
    draws=[]
    for _ in range(1000):
        sample=clusters[rng.integers(0,len(clusters),len(clusters))].sum(axis=0)
        draws.append(sample[0]/sample[1])
    return {"outcome":outcome,"comparison":comparison,"reference":"No Altitude",
            "delta":float(clusters[:,0].sum()/clusters[:,1].sum()),"ci_low":float(np.quantile(draws,.025)),
            "ci_high":float(np.quantile(draws,.975)),"n_pitchers":len(clusters),"n_matched_cells":len(pairs),
            "n_low":int(pairs.size_low.sum()),"n_high":int(pairs.size_high.sum()),"effective_weight":int(pairs.weight.sum())}


def pitcher_summary(scores):
    result=scores.groupby(["year","pitcher_anon_id","score_reference_id"]).agg(n_pitches=("PitchUID","size"),
           n_games=("game_anon_id","nunique"),stuff_plus=("stuff_plus","mean"),location_plus=("location_plus","mean"),
           pitching_plus=("pitching_plus","mean"),p_whiff=("p_whiff","mean"),p_whiff_given_swing=("p_whiff_given_swing","mean")).reset_index()
    rng=np.random.default_rng(910)
    intervals={}
    for key,g in scores.groupby(["year","pitcher_anon_id","score_reference_id"]):
        game=g.groupby("game_anon_id").agg(n=("PitchUID","size"),total=("pitching_plus","sum")).to_numpy()
        if len(game)<2:
            intervals[key]=[np.nan,np.nan]
            continue
        indices=rng.integers(0,len(game),size=(400,len(game)))
        values=game[indices].sum(axis=1)
        ci=np.quantile(values[:,1]/values[:,0],[.025,.975])
        intervals[key]=ci
    result["ci_low"]=[intervals[(r.year,r.pitcher_anon_id,r.score_reference_id)][0] for r in result.itertuples()]
    result["ci_high"]=[intervals[(r.year,r.pitcher_anon_id,r.score_reference_id)][1] for r in result.itertuples()]
    result["pitching_plus_shrunk"]=100+(result.pitching_plus-100)*result.n_pitches/(result.n_pitches+100)
    result["eligible"]=(result.n_pitches>=100)&(result.n_games>=5)
    return result


def main():
    OUT.mkdir(exist_ok=True)
    raw=v5.prepare_raw(v5.read_parquet("stuff_model_df.parquet"))
    raw["HB_normalized"]=raw.HorzBreak*np.where(raw.PitcherThrows.eq("Left"),-1,1)
    raw["whiff_swing"]=raw.is_whiff.where(raw.is_swing.eq(1))
    environmental=[]
    for typ,group in [("All",raw),*list(raw.groupby("AutoPitchType"))]:
        for category in ["Medium Altitude","Extreme Altitude"]:
            for outcome in ["is_whiff","whiff_swing","home_run","run_value_proxy","InducedVertBreak","HB_normalized"]:
                result=paired_environment(group,outcome,category)
                if result: environmental.append({"pitch_type":typ,**result})
    pd.DataFrame(environmental).to_csv(OUT/"entorno_ajustado.csv",index=False)
    raw.groupby(["year","altitude_category","AutoPitchType"]).agg(n=("PitchUID","size"),
        pitchers=("pitcher_anon_id","nunique"),whiff=("is_whiff","mean"),hr=("home_run","mean"),rv=("run_value_proxy","mean")).reset_index().to_csv(OUT/"entorno_descriptivo.csv",index=False)
    scores=v5.read_parquet("stuff_plus_output_v8/scores_pitch_v8.parquet")
    pitchers=pitcher_summary(scores)
    pitchers.to_csv(OUT/"pitchers_v8.csv",index=False)
    arsenal=pd.read_csv("stuff_plus_output_v8/arsenal_con_incertidumbre.csv")
    arsenal.to_csv(OUT/"arsenal_v8.csv",index=False)
    features=["PitchUID","PitcherThrows","BatterSide","RelSpeed","SpinRate","InducedVertBreak","HB_normalized","RelHeight","RelSide","Extension"]
    joined=scores.merge(raw[features],on="PitchUID",validate="one_to_one")
    mapping=joined.groupby(["pitcher_anon_id","AutoPitchType","PitcherThrows","altitude_category"]).agg(n=("PitchUID","size"),
        HB=("HB_normalized","mean"),IVB=("InducedVertBreak","mean"),velocity=("RelSpeed","mean"),spin=("SpinRate","mean"),
        stuff_plus=("stuff_plus","mean"),pitching_plus=("pitching_plus","mean"),p_whiff_given_swing=("p_whiff_given_swing","mean")).reset_index()
    mapping.to_csv(OUT/"mapa_movimiento.csv",index=False)
    profiles=[]
    for key,g in joined.groupby(["AutoPitchType","PitcherThrows","altitude_category"]):
        elite=g.loc[g.pitching_plus>=g.pitching_plus.quantile(.9)]
        if len(elite)<100 or elite.pitcher_anon_id.nunique()<3: continue
        for feature in ["RelSpeed","SpinRate","InducedVertBreak","HB_normalized","RelHeight","Extension"]:
            q=elite[feature].quantile([.25,.5,.75]).to_numpy()
            profiles.append(dict(zip(["pitch_type","hand","environment"],key))|{"feature":feature,"q25":q[0],"median":q[1],"q75":q[2],"n":len(elite),"pitchers":elite.pitcher_anon_id.nunique()})
    pd.DataFrame(profiles).to_csv(OUT/"perfiles_fisicos_descriptivos.csv",index=False)
    reliable=pitchers.loc[(pitchers.n_pitches>=300)&(pitchers.n_games>=5)].copy()
    promising=reliable.sort_values("pitching_plus_shrunk",ascending=False).iloc[0]
    cautious=reliable.loc[reliable.pitcher_anon_id.ne(promising.pitcher_anon_id)].copy()
    cautious["gap"]=cautious.stuff_plus-cautious.pitching_plus
    caution=cautious.sort_values("gap",ascending=False).iloc[0]
    sparse=pitchers.loc[(pitchers.n_pitches<50)&(~pitchers.eligible)].sort_values("n_pitches",ascending=False).iloc[0]
    cases=[]
    for label,row,reason in [("Revisar",promising,"Mayor Pitching+ regularizado entre muestras de al menos 300 pitches y cinco juegos."),
                              ("Cautela",caution,"Mayor diferencia entre Stuff+ y Pitching+ entre muestras amplias: revisar ubicación y contexto."),
                              ("Información insuficiente",sparse,"Menos de 50 pitches; solicitar una muestra adicional antes de comparar talento.")]:
        cases.append({"category":label,"reason":reason,"pitcher":str(row.pitcher_anon_id),"n_pitches":int(row.n_pitches),"n_games":int(row.n_games),
                      "stuff_plus":float(row.stuff_plus),"pitching_plus":float(row.pitching_plus),"ci_low":float(row.ci_low) if pd.notna(row.ci_low) else None,"ci_high":float(row.ci_high) if pd.notna(row.ci_high) else None})
    v6.json_write(OUT/"casos_scouting.json",cases)
    v6.json_write(OUT/"analisis_manifest.json",{"source_sha256":v6.file_hash("stuff_model_df.parquet"),"v8_bundle_sha256":v6.file_hash("stuff_plus_output_v8/bundle.json"),
        "script_sha256":v6.file_hash(__file__),"environment_rows":len(environmental),"scored_rows":len(scores),"pitcher_rows":len(pitchers),
        "excluded_missing_pitcher_scores":int(scores.pitcher_anon_id.isna().sum()),"environment_is_association":True,"multiple_comparisons_exploratory":True})
    print(f"Análisis completo: {len(environmental)} contrastes, {len(pitchers)} pitchers, tres casos",flush=True)


if __name__=="__main__": main()
