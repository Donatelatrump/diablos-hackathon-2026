"""Revisa el estilo del texto que ve el lector (HTML del documento, del reporte o del dashboard).

Reglas de la entrega: sin guiones de ningún tipo entre palabras, sin guiones largos, sin dos puntos,
sin punto y coma, sin asteriscos ni frases de relleno. El código, las fórmulas y los signos de menos
de los números (−2.3) no son prosa y no se revisan.

  python3 docs/estilo.py entrega/documento_tecnico.html entrega/reporte.html
  python3 docs/estilo.py --texto archivo.txt
"""
import html as H
import re
import sys

RELLENO = [
    "es importante", "cabe destacar", "como podemos ver", "como se puede ver", "vale la pena", "sin duda",
    "en resumen", "en conclusión", "revolucionari", "de vanguardia", "innovador", "potenciar", "optimizar",
    "sinergia", "game changer", "no sólo", "no solo", "fascinante", "exploremos", "a continuación",
    "cabe mencionar", "es crucial", "clave para", "robusto",
]
REGLAS = [
    ("guion largo", re.compile(r"[—–]")),
    ("guion entre palabras", re.compile(r"(?<=[A-Za-zÁÉÍÓÚáéíóúñÑ0-9])-(?=[A-Za-zÁÉÍÓÚáéíóúñÑ])")),
    ("guion suelto", re.compile(r"(?:^|\s)-(?=\s)")),
    ("dos puntos", re.compile(r"(?<!\d):(?!\d)")),
    ("punto y coma", re.compile(r";")),
    ("asterisco", re.compile(r"\*")),
]


def texto_visible(html: str) -> str:
    html = re.sub(r"<(script|style|pre|code|title|head)\b.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r'<span class="katex(?:-display)?".*?</span></span></span>', " ", html, flags=re.S)
    html = re.sub(r"<math.*?</math>", " ", html, flags=re.S)
    html = re.sub(r"<br\s*/?>|</(p|div|li|h\d|tr|td|th|section|figcaption)>", "\n", html)
    html = re.sub(r"<[^>]+>", " ", html)
    return H.unescape(html)


def revisar(texto: str, nombre: str) -> int:
    n = 0
    for i, linea in enumerate(texto.splitlines(), 1):
        l = re.sub(r"\s+", " ", linea).strip()
        if not l:
            continue
        for regla, rx in REGLAS:
            for m in rx.finditer(l):
                a = max(0, m.start() - 40)
                print(f"{nombre}:{i} [{regla}] …{l[a:m.end() + 40]}…")
                n += 1
        bajo = l.lower()
        for f in RELLENO:
            if re.search(r"(?<![a-záéíóúñ])" + re.escape(f), bajo):
                print(f"{nombre}:{i} [relleno: {f}] {l[:120]}")
                n += 1
    return n


if __name__ == "__main__":
    total = 0
    args = sys.argv[1:]
    if args and args[0] == "--texto":
        for f in args[1:]:
            total += revisar(open(f).read(), f)
    else:
        for f in args:
            total += revisar(texto_visible(open(f).read()), f)
    print(f"\n{total} problemas")
    sys.exit(1 if total else 0)
