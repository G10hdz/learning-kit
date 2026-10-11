#!/usr/bin/env bash
# install.sh — deja el kit listo por pisos. Idempotente; corre lo que falte.
#
#   ./install.sh          instala todo lo disponible
#   ./install.sh check    solo verifica requisitos, no instala nada
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
CHECK_ONLY="${1:-}"

say()  { printf '\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '  ok  %s\n' "$*"; }
miss() { printf '  --  %s\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

say "requisitos base"
have python3 && ok "python3 $(python3 --version 2>&1 | awk '{print $2}')" || miss "python3 FALTA (>=3.11)"
have uv      && ok "uv"      || miss "uv no esta — instala: curl -LsSf https://astral.sh/uv/install.sh | sh"
have node    && ok "node $(node --version 2>/dev/null)" || miss "node no esta (solo hace falta para explainers/tests de practice)"
have nlm     && ok "nlm $(nlm --version 2>/dev/null | head -1)" || miss "nlm no esta — instala: uv tool install notebooklm-mcp-cli && nlm login"
have pdflatex && ok "pdflatex" || miss "pdflatex no esta (opcional, compila los briefs: brew install --cask mactex / apt install texlive)"

[ "$CHECK_ONLY" = "check" ] && exit 0

say "acquisition/ (founder-guide)"
if have uv; then
  (cd "$ROOT/acquisition" && uv venv --quiet && uv pip install --quiet -e .) \
    && ok "editable install en acquisition/.venv" \
    || miss "fallo uv pip install -e acquisition"
else
  miss "sin uv: cd acquisition && python3 -m venv .venv && .venv/bin/pip install -e ."
fi

say "production/ (capital-cultural)"
ok "scripts listos; vault/ se crea solo al primer uso (ver production/README.md)"
have nlm || miss "nlm requerido para los flujos de NotebookLM"

say "practice/ (hypatia)"
ok "apps estaticas: abre practice/index.html o sirvelas con python3 -m http.server"

say "memory/ (vault-sync)"
if [ ! -f "$HOME/.config/vault-sync/config.json" ]; then
  mkdir -p "$HOME/.config/vault-sync"
  cp "$ROOT/memory/config.example.json" "$HOME/.config/vault-sync/config.json"
  ok "config ejemplo en ~/.config/vault-sync/config.json — editala con tus rutas"
else
  ok "config ya existe"
fi

say "surface/ (hub)"
if have node; then
  (cd "$ROOT/surface" && ./scripts/bundle.sh) && ok "site/ construido" || miss "bundle fallo (revisa PLAYER_DIR si quieres explainers)"
else
  miss "sin node: copia a mano lo de practice/ a un directorio servido"
fi

say "listo"
echo "Siguiente: REQUIREMENTS.md por piso, y docs/architecture.md para el mapa completo."
