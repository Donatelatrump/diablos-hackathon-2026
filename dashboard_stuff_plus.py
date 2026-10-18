"""Entrada principal: usa v6 verificada o conserva la interfaz v5."""
from pathlib import Path
import runpy
import json

root = Path(__file__).resolve().parent
version = "v6" if (root / "stuff_plus_output_v6" / "verificacion.json").exists() else "v5"
if (root / "stuff_plus_output_v7" / "verificacion.json").exists():
    metadata = json.loads((root / "stuff_plus_output_v7" / "bundle.json").read_text(encoding="utf-8"))
    if metadata["stack"]["chosen"]["promoted"] or any(item["selected"] != "identity" for item in metadata["calibrations"].values()):
        version = "v7"
if (root / "stuff_plus_output_v8" / "verificacion.json").exists():
    metadata = json.loads((root / "stuff_plus_output_v8" / "bundle.json").read_text(encoding="utf-8"))
    if any(item["promoted"] for item in metadata["selection"].values()):
        version = "v8"
runpy.run_path(str(root / f"dashboard_stuff_plus_{version}.py"), run_name="__main__")
