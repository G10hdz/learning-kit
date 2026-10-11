# Adquisición de fuentes

Cómo entran libros y papers al sistema. El pipeline no distingue el origen de un archivo: lo que llega al inbox es adquisición declarada propia.

## Comandos

```bash
python3 scripts/ingest.py list            # estado del catálogo
python3 scripts/ingest.py add vc-05       # URL del catálogo o inbox -> archivo + Calibre
python3 scripts/ingest.py add --inbox     # procesa todo vault/inbox/
python3 scripts/ingest.py study ivy-01    # archivo -> NotebookLM (libreta por categoría)
python3 scripts/ingest.py pending         # pendientes + link de búsqueda manual
```

## Flujo

1. **Entrada**: `add <ID>` descarga por la URL del catálogo si es libre (Gutenberg, arXiv, PDFs oficiales) o toma el archivo de `vault/inbox/<ID>_<nombre>.<ext>` para lo conseguido a mano.
2. **Calibre**: el archivo se scp'a al host de Calibre (`~/cwa/ingest/`). Calibre-Web-Automated (Docker, puerto 8093 solo vía Tailscale) convierte formato, completa metadata, lo importa a la librería y puede enviarlo al Kindle por correo.
3. **Estudio**: `study <ID>` lo sube a NotebookLM con `nlm` (una libreta por categoría, ID guardado en el catálogo).
4. **Catálogo**: `_catalogo.md` refleja estado (`calibre`, `ingerido`), archivo y libreta.

## Paso humano

Lo que no tiene descarga directa entra a mano: `ingest.py pending` imprime un link de búsqueda por título, la persona consigue el archivo y lo suelta en `vault/inbox/<ID>_<nombre>.<ext>`. Luego `ingest.py add <ID>` lo mete a Calibre y al catálogo.

Lo que te guste, se compra (Kindle/físico); el sistema ya tiene el archivo trabajando mientras tanto.

## Infra

- CWA: `~/cwa/docker-compose.yml` en el host de Calibre, imagen `crocodilestick/calibre-web-automated`, librería `~/Calibre Library`, UI en `http://<host>:8093` (solo Tailscale). Cambiar contraseña admin en el primer login.
- onefilellm: `uv tool install` desde `~/tools/onefilellm` en la Mac; convierte arXiv/DOI/YouTube/docs a un solo texto para LLM.
