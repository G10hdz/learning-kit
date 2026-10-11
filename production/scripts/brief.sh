#!/usr/bin/env bash
# brief.sh <notebook-id> <categoria> <tema> <pregunta>
# Query NotebookLM y guarda solo el .answer como resumen normalizado.
# El JSON crudo (citations) queda en /tmp para consulta, nunca en el vault.
set -euo pipefail
id="$1"; cat="$2"; tema="$3"; q="$4"
out="vault/summaries/$cat/$(date +%F)-$tema.md"
mkdir -p "vault/summaries/$cat"
nlm notebook query "$id" "$q" > /tmp/nlm-raw.json
jq -r '.answer' /tmp/nlm-raw.json > "$out"
echo "$out  ($(wc -l < "$out") lineas; JSON crudo en /tmp/nlm-raw.json)"
