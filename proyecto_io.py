"""Local data discovery and actionable diagnostics for Git LFS checkouts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"


def is_lfs_pointer(path):
    path = Path(path)
    if not path.is_file():
        return False
    with path.open("rb") as stream:
        return stream.read(len(LFS_HEADER)) == LFS_HEADER


def require_local_file(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No existe {path}. Consulta docs/guias/GUIA_PROYECTO.md.")
    if is_lfs_pointer(path):
        raise ValueError(
            f"{path} es un puntero Git LFS, no el archivo completo. "
            "Usa git lfs pull con acceso al repositorio, o coloca el parquet en "
            "Data/stuff_model_df.parquet y usa --parquet Data/stuff_model_df.parquet."
        )
    return path


def data_path(explicit=None):
    if explicit is not None:
        return require_local_file(explicit)
    for path in [ROOT / "Data/stuff_model_df.parquet", ROOT / "stuff_model_df.parquet"]:
        if path.is_file() and not is_lfs_pointer(path):
            return path
    return require_local_file(ROOT / "stuff_model_df.parquet")


def bundle_ready(path):
    path = Path(path)
    models = list(path.rglob("*.cbm")) if path.is_dir() else []
    return (path / "bundle.json").is_file() and bool(models) and all(
        not is_lfs_pointer(model) for model in models
    )
