# learning-surface

Piso **surface** del learning-kit: hub web móvil servido dentro de la
tailnet. Junta las apps de práctica en un solo lugar alcanzable desde
teléfono, tablet y compu, sin exponer nada a internet público.

```
scripts/bundle.sh   # construye site/: hub + ai-coach dist + apps Hypatia + explainers
scripts/serve.sh    # publica site/ via tailscale serve (HTTPS tailnet)
scripts/serve.sh off
```

La lectura de notas y briefs va por Obsidian (vault sincronizado por
Syncthing). El audio hands-free llega por la carpeta `audiobooks`
(ver `scripts/` en `production/`).

## Diseño

- **Nada público por diseño.** `tailscale serve` solo responde dentro de
  la tailnet; el contenido personal nunca toca una URL pública.
- **El sitio es un build artifact.** `site/` se regenera con `bundle.sh`;
  no se commitea.
- **Apps 100% cliente.** Todo corre en el dispositivo (localStorage,
  transformers.js); el server solo sirve archivos estáticos.
- **Explainers por allowlist.** `explainers.txt` lista los modelos de
  pr-explainer que entran al sitio, y `bundle.sh` los construye con el
  player del skill (`PLAYER_DIR`). Lo que no esté listado no se publica.

Parte del learning-kit: ver `../REQUIREMENTS.md`.

## Licencia

Apache 2.0, Positronica Labs.
