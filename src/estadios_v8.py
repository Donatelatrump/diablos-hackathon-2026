"""Enlaces comprobados juego-estadio; nunca deduce identidad desde altitud."""
from pathlib import Path
import argparse
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def attach_stadiums(games, mapping, catalog):
    """Una correspondencia explícita por año/juego; no por proximidad de altitud."""
    keys = ["year", "game_anon_id"]
    required = keys + ["stadium_id", "source_url"]
    if not set(required).issubset(mapping.columns):
        raise ValueError("El mapeo requiere year, game_anon_id, stadium_id y source_url.")
    mapping = mapping[required].copy()
    if mapping[keys].isna().any().any() or mapping.duplicated(keys).any():
        raise ValueError("Cada juego debe aparecer una sola vez, con año e ID completos.")
    if mapping["stadium_id"].isna().any() or not mapping.stadium_id.isin(catalog.stadium_id).all():
        raise ValueError("Hay estadios ausentes del catálogo.")
    if not mapping.source_url.fillna("").str.match(r"https?://\S+$").all():
        raise ValueError("Cada asignación necesita una URL de evidencia verificable.")
    known = games[keys].drop_duplicates()
    if len(mapping.merge(known, on=keys, how="inner")) != len(mapping):
        raise ValueError("Hay juegos que no pertenecen al dataset/año indicado.")
    joined = games.merge(mapping, on=keys, how="left", validate="many_to_one")
    joined = joined.merge(catalog[["stadium_id", "stadium", "altitude_m", "altitude_source"]],
                          on="stadium_id", how="left", validate="many_to_one")
    joined["stadium_status"] = joined.stadium_id.notna().map({True: "mapeo_documentado", False: "sin_identificar"})
    return joined


def audit(raw):
    categories = raw.groupby(["year", "altitude_category"], dropna=False).agg(
        pitches=("PitchUID", "size"), games=("game_anon_id", "nunique")).reset_index()
    return {
        "pitches": len(raw), "games": int(raw.game_anon_id.nunique()),
        "columns": list(raw.columns),
        "mixed_category_games": int((raw.groupby("game_anon_id").altitude_category.nunique() > 1).sum()),
        "missing_altitude_pitches": int(raw.altitude_category.isna().sum()),
        "categories": categories.astype(object).where(pd.notna(categories), None).to_dict("records"),
        "stadium_identifiable_from_altitude_alone": False,
        "reason": "IDs anónimos sin fecha, equipos o clave pública de juego; tres categorías no identifican un estadio.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapeo", type=Path, help="CSV documentado: year,game_anon_id,stadium_id,source_url")
    args = parser.parse_args()
    from entrenar_stuff_plus_v5 import read_parquet
    raw = read_parquet(ROOT / "stuff_model_df.parquet")
    catalog = pd.read_csv(ROOT / "entrega_v8/estadios_altitudes.csv")
    mapping = pd.read_csv(args.mapeo) if args.mapeo else pd.DataFrame(columns=["year", "game_anon_id", "stadium_id", "source_url"])
    games = raw.groupby(["year", "game_anon_id", "altitude_category"], dropna=False).size().rename("pitches").reset_index()
    linked = attach_stadiums(games, mapping, catalog)
    # Identificadores de juego permanecen locales, fuera del ZIP de resultados.
    linked.to_csv(ROOT / "stuff_plus_output_v8/estadios_por_juego.csv", index=False)
    summary = audit(raw)
    summary.update(mapped_games=int(linked.stadium_id.notna().sum()),
                   mapped_pitches=int(linked.loc[linked.stadium_id.notna(), "pitches"].sum()))
    (ROOT / "entrega_v8/AUDITORIA_ESTADIOS.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ["pitches", "games", "mapped_games", "mapped_pitches", "missing_altitude_pitches"]}))


if __name__ == "__main__":
    main()
