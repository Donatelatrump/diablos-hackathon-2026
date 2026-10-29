"""Verificación reproducible de decisiones e inferencia v8."""
import json
from pathlib import Path
import numpy as np
import entrenar_stuff_plus_v8 as v8


def verify(out=Path("stuff_plus_output_v8"), source=Path("stuff_model_df.parquet")):
    v5,v6,v7=v8.v5,v8.v6,v8.v7
    meta=json.loads((out/"bundle.json").read_text(encoding="utf-8"))
    assert meta==json.loads((out/"seleccion_congelada.json").read_text(encoding="utf-8"))
    protocol=json.loads((out/"protocolo.json").read_text(encoding="utf-8"))
    assert v6.file_hash(out/"protocolo.json")==meta["protocol_hash"]
    assert v6.file_hash(source)==protocol["source_sha256"]
    for file,digest in protocol["code_hashes"].items(): assert v6.file_hash(file)==digest
    for file,digest in meta["model_hashes"].items(): assert v6.file_hash(out/file)==digest
    assert v6.file_hash(out/"parent_v7/bundle.json")==meta["parent_hash"]
    bundle=v8.load_bundle(out)
    raw=v5.prepare_raw(v6.read_seasons(source,2025))
    frame=v7.partition_games(v6.enhance(v5.historical_features(raw)))
    parts=v5.read_parquet(out/"particiones.parquet").set_index("PitchUID")
    assert set(parts.index)==set(frame.PitchUID)
    assert parts.loc[frame.PitchUID,"partition"].tolist()==frame.partition.tolist()
    assert not frame.PitchUID.duplicated().any()
    assert frame.groupby(["year","game_anon_id"]).partition.nunique().max()==1
    cal=frame.loc[frame.partition.eq("calibration")].reset_index(drop=True)
    sel=frame.loc[frame.partition.eq("selection")].reset_index(drop=True)
    tune=v8.selection_halves(sel)
    roles=v5.read_parquet(out/"seleccion_roles.parquet").set_index("PitchUID")
    assert roles.loc[sel.PitchUID,"role"].tolist()==np.where(tune,"tune","confirmation").tolist()
    decisions={}
    for task,spec in v7.COMPONENTS.items():
        table=v5.read_parquet(out/f"seleccion_{task}.parquet").set_index("PitchUID").loc[sel.PitchUID].reset_index()
        np.testing.assert_allclose(table[spec[0]],sel[spec[0]],equal_nan=True)
        cm,sm=v5.eligible(cal,spec).to_numpy(),v5.eligible(sel,spec).to_numpy()
        columns=[c for c in table if c=="control" or "|" in c]
        options={c:table[c].to_numpy() for c in columns}
        choice=v8.choose(sel.loc[sm,spec[0]].to_numpy(),{k:p[sm] for k,p in options.items()},tune[sm],sel.loc[sm,"year"].to_numpy())
        expected=meta["selection"][task]
        assert choice["candidate"]==expected["candidate"]
        if spec[3]=="classification":
            mask=sm&~tune
            passes=v7.log_loss(sel.loc[mask,spec[0]],options[choice["candidate"]][mask])<=v7.log_loss(sel.loc[mask,spec[0]],options["control"][mask])*1.0015
            choice["promoted"]=choice["promoted"] and passes
        assert choice["promoted"]==expected["promoted"]
        sample=sel.iloc[:100]
        control=v6.predict(bundle[2][1][task],spec,sample)
        preds=v8.candidates(sample,task,bundle[1],control)
        np.testing.assert_allclose(control,table.control.iloc[:100],atol=1e-10)
        for key,p in preds.items(): np.testing.assert_allclose(p,table[key+"|raw"].iloc[:100],atol=1e-10)
        if "|sigmoid" in choice["candidate"]:
            control_cal=v6.predict(bundle[2][1][task],spec,cal)
            key=choice["candidate"].split("|")[0]
            cp=v8.candidates(cal,task,bundle[1],control_cal)[key]
            mapping=v7.fit_calibrators(cal.loc[cm,spec[0]],cp[cm])["sigmoid"]
            np.testing.assert_allclose(v7.apply_calibrator(preds[key],mapping),table[choice["candidate"]].iloc[:100],atol=1e-9)
            assert mapping==expected["calibrator"]
        decisions[task]={"candidate":choice["candidate"],"promoted":bool(choice["promoted"])}
    data=v6.read_seasons(source,2026)
    test=data.loc[data.year.eq(2026)].reset_index(drop=True)
    scores=v5.read_parquet(out/"scores_pitch_v8.parquet")
    assert len(scores)==len(test) and set(scores.PitchUID)==set(test.PitchUID)
    assert not scores.PitchUID.duplicated().any()
    cols=[c for c in scores if c.startswith(("p_","pred_"))]+v6.SCORE_COLUMNS
    assert np.isfinite(scores[cols].to_numpy()).all()
    sample=test.sample(100,random_state=808).reset_index(drop=True)
    live=v8.infer(sample,bundle)
    saved=scores.set_index("PitchUID").loc[sample.PitchUID]
    np.testing.assert_allclose(live[cols],saved[cols],atol=1e-9)
    changed=sample.copy()
    changed["PlateLocHeight"],changed["PlateLocSide"],changed["Balls"],changed["Strikes"]=5.,2.,3,2
    changed["BatterSide"],changed["altitude_category"]="Left","Extreme Altitude"
    physics=["stuff_plus","p_whiff","p_whiff_given_swing","p_ball_in_play","pred_stuff_run_value"]
    np.testing.assert_allclose(live[physics],v8.infer(changed,bundle)[physics],atol=1e-9)
    missing=sample.drop(columns=v8.EXTRA)
    old=v7.infer(missing,bundle[2])
    np.testing.assert_allclose(v8.infer(missing,bundle)[cols],old[cols],atol=1e-9)
    mixed=sample.copy()
    mixed.loc[0,"ZoneSpeed"]=np.nan
    mixed_output=v8.infer(mixed,bundle)
    mixed_parent=v7.infer(mixed.iloc[:1],bundle[2])
    np.testing.assert_allclose(mixed_output.iloc[:1][cols],mixed_parent[cols],atol=1e-9)
    np.testing.assert_allclose(mixed_output.iloc[1:][cols],live.iloc[1:][cols],atol=1e-9)
    inputs=list(dict.fromkeys([c for c in v5.PHYSICAL if c in sample]+v6.EXTRA_RAW+v8.EXTRA+
          ["SpinAxis","PitchUID","pitcher_anon_id","PlateLocHeight","PlateLocSide","Balls","Strikes","BatterSide","altitude_category"]))
    np.testing.assert_allclose(v8.infer(sample[inputs],bundle)[cols],live[cols],atol=1e-9)
    np.testing.assert_allclose(v8.infer(sample.iloc[:1],bundle)[cols],live.iloc[:1][cols],atol=1e-9)
    np.testing.assert_allclose(live.pitching_plus,v7.infer(sample,bundle[2]).pitching_plus,atol=1e-9)
    checks={"rows":len(scores),"hashes_match":True,"same_training_partitions_as_v7":True,
            "games_disjoint":True,"selection_reproduced":True,"prediction_reproduced":True,
            "fallback_exact":True,"physical_invariance":True,"outcomes_not_required":True,
            "batch_invariant":True,"decisions":decisions,"benchmark_reused":True}
    v6.json_write(out/"verificacion.json",checks)
    print(json.dumps(checks,indent=2))


if __name__=="__main__": verify()
