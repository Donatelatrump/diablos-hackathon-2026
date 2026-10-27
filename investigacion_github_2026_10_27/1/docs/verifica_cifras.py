"""¿Qué cifras del documento técnico ya no salen de los datos?

Después de reentrenar, casi todas las cifras del texto cambian. Este script saca cada número con decimales de
docs/documento_tecnico.md (sin fórmulas ni código) y lo busca entre todos los valores de los JSON de artifacts/ y de
app/public/data/, redondeados a los mismos decimales, con y sin signo, y también multiplicados por 100 (porcentajes y
carreras por cada 100). Lista los que no encuentra, con su línea, para que los revises a mano.

  python3 docs/verifica_cifras.py

No es una prueba perfecta. Un número viejo puede coincidir por casualidad con otro valor, y uno correcto puede ser
una resta o una razón que no está guardada tal cual. Sirve para no dejar ninguna cifra vieja sin revisar.
"""
import json
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def valores(x, out):
    if isinstance(x, dict):
        for v in x.values():
            valores(v, out)
    elif isinstance(x, list):
        for v in x:
            valores(v, out)
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        out.append(float(x))


def main() -> None:
    nums: list[float] = []
    for carpeta in (RAIZ / "artifacts", RAIZ / "app" / "public" / "data"):
        for f in carpeta.glob("*.json"):
            if f.name.startswith("model_"):
                continue
            try:
                valores(json.loads(f.read_text()), nums)
            except Exception:
                pass
    conocidos: dict[int, set[str]] = {d: set() for d in range(0, 6)}
    for v in nums:
        for k in (1, 100, -1, -100):
            for d in conocidos:
                conocidos[d].add(f"{abs(v * k):.{d}f}")

    md = (RAIZ / "docs" / "documento_tecnico.md").read_text()
    md = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), md, flags=re.S)
    md = re.sub(r"\$\$.+?\$\$", lambda m: "\n" * m.group(0).count("\n"), md, flags=re.S)
    faltan = 0
    for i, linea in enumerate(md.splitlines(), 1):
        texto = re.sub(r"\$[^$]*\$", " ", linea)
        for m in re.finditer(r"(?<![\w.])(\d{1,3}(?:,\d{3})*\.\d+|\d+\.\d+)(?![\w.])", texto):
            t = m.group(1).replace(",", "")
            d = len(t.split(".")[1])
            if t not in conocidos.get(min(d, 5), set()):
                faltan += 1
                print(f"línea {i:4d}  {m.group(1):>10}  {linea.strip()[:110]}")
    print(f"\n{faltan} cifras sin respaldo directo en los JSON. Revisa cada una contra los artefactos nuevos.")


if __name__ == "__main__":
    main()
