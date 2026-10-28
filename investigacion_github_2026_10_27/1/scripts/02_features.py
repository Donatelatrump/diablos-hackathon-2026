"""Etapa 2: secuencia, features y objetivos. Produce artifacts/model_frame.pkl."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.stuffplus import features, physics, sequence, targets  # noqa: E402

ART = Path(__file__).resolve().parents[1] / "artifacts"


def main() -> None:
    df = pd.read_pickle(ART / "pitches_rho.pkl")
    print(f"{len(df):,} lanzamientos")

    df = sequence.add_sequence(df)
    print(f"turnos reconstruidos: {df.pa_id.nunique():,} "
          f"(media {len(df)/df.pa_id.nunique():.2f} lanzamientos por turno)")

    pa = sequence.pa_outcome(df)
    df, count_value = targets.run_values(df, pa)
    df = targets.build(df)

    aero = physics.decompose(df)
    df = features.add_shape(df, aero)
    df = features.add_arsenal(df)

    df.to_pickle(ART / "model_frame.pkl")
    (ART / "count_value.json").write_text(
        json.dumps({k: round(float(v), 4) for k, v in count_value.items()}, indent=2)
    )

    print("\nvalor por conteo (runs sobre el promedio):")
    print(count_value.round(4).to_string())
    print("\nresultado de turno:")
    print(pa.pa_event.value_counts().to_string())
    print("\nobjetivos (media sobre su subconjunto):")
    ys = [c for c in df.columns if c.startswith("y_")]
    print(df[ys].mean().round(4).to_string())
    print(f"\nrv por lanzamiento: media {df.rv.mean():.5f}  sd {df.rv.std():.4f}")


if __name__ == "__main__":
    main()
