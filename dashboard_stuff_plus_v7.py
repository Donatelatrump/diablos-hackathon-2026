"""Interfaz v7 sobre el flujo compartido de simulación y arsenal."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("dashboard_stuff_plus_v6.py")),
               init_globals={"MODEL_VERSION": 7}, run_name="__main__")
