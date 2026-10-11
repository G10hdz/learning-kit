#!/usr/bin/env bash
# tex.sh <ruta.tex> -> compila en $CALIBRE_HOST (pdflatex) y devuelve el PDF junto al .tex
# El .tex puede usar \input{brief-preamble.tex}; este script lo envia junto.
set -euo pipefail
host="${CALIBRE_HOST:?define CALIBRE_HOST (host con pdflatex)}"
tex="$1"; dir=$(dirname "$tex"); base=$(basename "$tex" .tex)
pre="templates/brief-preamble.tex"
scp -q "$tex" $host:/tmp/
[ -f "$pre" ] && scp -q "$pre" $host:/tmp/
ssh $host "cd /tmp && pdflatex -interaction=nonstopmode '$base.tex' >/dev/null 2>&1; pdflatex -interaction=nonstopmode '$base.tex' >/dev/null 2>&1; ls '$base.pdf'" >/dev/null
scp -q "$host:/tmp/$base.pdf" "$dir/"
echo "$dir/$base.pdf"
