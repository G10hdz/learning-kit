# Adquisición de fuentes

Como entran libros, papers y videos al sistema. El pipeline no distingue el origen del archivo: lo que llega al inbox es adquisición declarada propia.

## Comandos

```bash
python3 scripts/acquire.py list            # estado del catálogo
python3 scripts/acquire.py add bus-01      # URL del catálogo o inbox -> archivo + Calibre
python3 scripts/acquire.py add --inbox     # procesa todo vault/inbox/
python3 scripts/acquire.py study bus-01    # archivo -> NotebookLM (libreta por sección)
python3 scripts/acquire.py pending         # pendientes + candidatos de resolvers
python3 scripts/acquire.py suggest --title "..." --author "..." --section 01-startup-negocio [--type book|video] [--url "..."]
```

## Flujo

1. **Sugerir**: `suggest` agrega una entrada al catálogo con estado `pendiente`. Sirve para libros o videos que alguien propone ingerir después.
2. **Entrada**: `add <ID>` descarga por la URL del catálogo si es libre (Gutenberg, arXiv, GitHub, PDFs oficiales) o toma el archivo de `vault/inbox/<ID>_<nombre>.<ext>` para lo conseguido a mano.
3. **Calibre**: el archivo se scp'a a `<calibre-host>:~/cwa/ingest/`. Calibre-Web-Automated (Docker, puerto 8093 solo vía Tailscale) convierte formato, completa metadata, lo importa a la librería y puede enviarlo al Kindle por correo.
4. **Estudio**: `study <ID>` lo sube a NotebookLM con `nlm` (una libreta por sección, ID guardado en el catálogo).
5. **Catálogo**: `docs/book-candidates.md` refleja estado (`pendiente`, `calibre`, `ingerido`), archivo y libreta.

## Paso humano

Lo que no tiene descarga directa entra a mano. `acquire.py pending` imprime, por cada pendiente, los candidatos que resuelven los resolvers instalados: por defecto una búsqueda en Open Library por título. La persona consigue el archivo y lo suelta en `vault/inbox/<ID>_<nombre>.<ext>`; `acquire.py add <ID>` lo archiva y lo manda a Calibre.

Resolvers adicionales se enchufan como plugins: un `.py` con `resolve(row) -> Iterable[Candidate|dict]` en `~/.config/founder-guide/resolvers/` (o `$FOUNDER_GUIDE_RESOLVER_DIR`). Los plugins viven fuera del repo: cada instalación decide qué fuentes resuelve. Contrato en `scripts/resolvers.py`.

Lo que te guste, se compra (Kindle/físico); el sistema ya tiene el archivo trabajando mientras tanto.

## Sugerir fuentes

```bash
# libro
python3 scripts/acquire.py suggest --title "The Lean Startup" --author "Eric Ries" --section 01-startup-negocio

# video
python3 scripts/acquire.py suggest --title "How to Start a Startup" --author "YC" --section 01-startup-negocio --type video --url "https://youtube.com/playlist?list=..."

# paper abierto
python3 scripts/acquire.py suggest --title "Attention Is All You Need" --author "Vaswani et al" --section 03-ai --url "https://arxiv.org/abs/1706.03762"
```

El ID se genera automáticamente según la sección (`bus-NN`, `des-NN`, `ai-NN`, `cod-NN`).

## Infra

- CWA: `~/cwa/docker-compose.yml` en el host de Calibre, imagen `crocodilestick/calibre-web-automated`, librería `~/Calibre Library`, UI en `http://<host>:8093` (solo Tailscale). Cambiar contraseña admin en el primer login.
- `nlm`: adaptador de NotebookLM. `nlm login --check` para verificar credenciales.

## Secciones del vault

| Prefijo | Sección | Tema |
|---|---|---|
| `bus-` | 01-startup-negocio | validación, ventas, teams, fundraising, ops |
| `des-` | 02-diseno | producto, UX, marca, research |
| `ai-` | 03-ai | LLMs, RAG, evals, uso interno |
| `cod-` | 04-codigo | lineamientos + destilados para agentes |
