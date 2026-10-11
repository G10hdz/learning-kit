#!/usr/bin/env bash
# voice-cast.sh <notebook-id> <slug-libro> <categoria>
# Pregunta a NotebookLM (que ya leyo el libro) por el perfil de narrador ideal
# y sugiere arquetipo/voz segun la tabla de vault/speech/audiobook-casting.json.
# La decision final se edita a mano en el JSON (columna voz / verificado).
set -euo pipefail
id="$1"; slug="$2"; cat="${3:-Código Comercial}"
q="Basandote en el autor y contenido de este libro, describe al narrador de audiolibro ideal en EXACTAMENTE esta linea y minusculas, sin puntos finales: genero=masculino|femenino; edad=joven|media|mayor; textura=grave|media|ligera; tono=cinico|medido|directo|calido; una palabra de contexto. Ejemplo: genero=masculino; edad=mayor; textura=grave; tono=cinico; rehenes"
nlm notebook query "$id" "$q" 2>/dev/null | jq -r '.answer' | head -2 > "/tmp/cast-$slug.txt"
echo "--- spec NLM ($slug):"; cat "/tmp/cast-$slug.txt"
echo "--- match arquetipo:"
spec=$(cat "/tmp/cast-$slug.txt" | tr '\n' ' ')
python3 - "$spec" "$slug" << 'EOF'
import json, sys
spec, slug = sys.argv[1].lower(), sys.argv[2]
d = json.load(open("vault/speech/audiobook-casting.json"))
puntos = {}
for arq, cfg in d["arquetipos"].items():
    keywords = cfg["pista"].split(", ")
    puntos[arq] = sum(1 for k in keywords if k and k in spec)
best = max(puntos, key=puntos.get)
print(f"{best} -> voz: {d['arquetipos'][best]['voz']} (alt: {d['arquetipos'][best]['alt']})")
print(f"edita vault/speech/audiobook-casting.json castings['{slug}'] si quieres otra")
EOF
