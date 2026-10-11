# vault-sync

Sincroniza notas Markdown a [ai-memory](https://github.com/G10hdz/ai-memory) por *lanes*: cada directorio mapea a un namespace, y solo lo declarado entra a la memoria de los agentes. Lo demás queda privado por omisión.

Un solo archivo, stdlib puro. Pensado para correr como cron/launchd cada N minutos.

## Uso

```bash
python3 vault_sync.py scan     # notas pendientes de sync (JSON)
python3 vault_sync.py sync     # escanea y guarda en ai-memory
python3 vault_sync.py status   # totales por namespace
python3 vault_sync.py check    # self-check
```

Requiere el CLI `ai-memory` en el PATH (`ai-memory store ...`).

## Configuración

`~/.config/vault-sync/config.json` (o `$VAULT_SYNC_CONFIG`):

```json
{
  "vault": "~/Obsidian/MyVault",
  "lanes": {
    "00-Inbox": "obsidian/inbox",
    "20-Study": "obsidian/study",
    "30-Projects": "obsidian/projects"
  },
  "external_lanes": {
    "~/projects/my-app": "obsidian/my-app"
  },
  "state_dir": "~/.cache/vault-sync"
}
```

- `lanes`: subdirectorios del vault → namespace.
- `external_lanes`: directorios fuera del vault (un repo de práctica, por ejemplo). Sus `.md` se indexan directo desde ahí con prefijo `<nombre-dir>/`.
- `$VAULT_PATH` sobreescribe `vault`.
- El estado vive en `<state_dir>/state.json` (hash por nota; solo re-sincroniza lo que cambió).

Se excluyen siempre: `.obsidian`, `.git`, `vendor`, `node_modules`, `Imports`, `graphify-out`, archivos que empiezan con `.` y otros directorios de tooling (ver `SKIP_DIRS`).

## Diseño

- **Sync por lanes, no por todo.** Lo consultable por agentes se declara; el resto no sale del vault.
- **El estado externo se indexa en su lugar.** Sistemas externos no se copian al vault: sus notas entran por `external_lanes`.
- **Sin daemon propio.** Es un script idempotente; el scheduler es launchd/cron del host.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Stdlib only; un stub de `ai-memory` reemplaza al binario real.

Parte del learning-kit (piso `memory/`).

## Licencia

Apache 2.0 — Positronica Labs.
