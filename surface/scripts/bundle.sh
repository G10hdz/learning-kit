#!/usr/bin/env bash
# bundle.sh — construye site/ con el hub + las apps de practice.
#
#   AI_COACH_DIR   repo ai-coach opcional (default <kit>/practice-coach si existe)
#   HYPATIA_DIR    apps estaticas    (default <kit>/practice)
#   PLAYER_DIR     player de pr-explainer (default ~/agent-configs/_shared/pr-explainer/player)
#   SURFACE_SITE   salida            (default <repo>/site, gitignored)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AI_COACH_DIR="${AI_COACH_DIR:-$ROOT/../practice-coach}"
HYPATIA_DIR="${HYPATIA_DIR:-$ROOT/../practice}"
SITE="${SURFACE_SITE:-$ROOT/site}"

rm -rf "$SITE"
mkdir -p "$SITE/hypatia"
cp "$ROOT/index.html" "$SITE/"

if [ -d "$AI_COACH_DIR/web" ]; then
  echo "== ai-coach web"
  mkdir -p "$SITE/coach"
  [ -d "$AI_COACH_DIR/web/node_modules" ] || npm --prefix "$AI_COACH_DIR/web" ci --silent
  npm --prefix "$AI_COACH_DIR/web" run build --silent
  cp -R "$AI_COACH_DIR/web/dist/." "$SITE/coach/"
else
  echo "== ai-coach no presente, se omite"
fi

echo "== hypatia"
for app in CubPrep SAA-C03 MLOps Flashcards shared; do
  [ -d "$HYPATIA_DIR/$app" ] && cp -R "$HYPATIA_DIR/$app" "$SITE/hypatia/$app"
done
cp "$HYPATIA_DIR"/favicon* "$HYPATIA_DIR"/apple-touch-icon.png "$SITE/" 2>/dev/null || true

echo "== explainers"
if [ -f "$ROOT/explainers.txt" ]; then
  node "$ROOT/scripts/explainers.mjs" "$ROOT/explainers.txt" "$SITE/explainers"
else
  echo "sin explainers.txt, se omiten (ver explainers.example.txt)"
fi

du -sh "$SITE"
echo "site listo: $SITE"
