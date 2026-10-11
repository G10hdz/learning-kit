# SPEC-010: migración de SQLite v1 a v2

**Dado** una base SQLite v1 creada directamente con las tablas `sources`,
`documents`, `segments` y `notes`, que contiene un video, un documento y un
segmento

**Cuando** se abre `SqliteStore` sobre esa base

**Entonces** la migración conserva las tablas v1 intactas con sus filas,
establece `PRAGMA user_version = 2` y proyecta una fila en
`knowledge_sources`, `knowledge_documents` y `knowledge_chunks`.

Contrato mínimo de las proyecciones:

- `knowledge_sources`: `source_id` = `youtube:video-1`, `source_type` =
  `youtube`, `external_id` = `video-1`, `canonical_uri` conserva la URL y
  `visibility_scope` = `shared`.
- `knowledge_documents`: `document_id` = `youtube:video-1:es:hash-1`,
  `content_hash` = `hash-1` y `active` = 1.
- `knowledge_chunks`: `chunk_id` conserva el `citation_id`, `locator_kind` =
  `timestamp` y los segundos originales.

**Y** al reabrir `SqliteStore` sobre la misma base la migración no duplica
filas en ninguna tabla de conocimiento.

La migración corre dentro de una transacción y es idempotente: `user_version`
ya vale 2 en una reapertura.

## SPEC-011: write-through mantiene la proyección

**Dado** un `SqliteStore` v2 vacío

**Cuando** los métodos existentes guardan una fuente, documento y segmento

**Entonces** las tablas `knowledge_*` reflejan esas filas antes de cerrar o
reabrir la conexión.

## SPEC-012: ingesta directa no deja documentos huérfanos

**Dado** un transcript ingerido sin una fila previa en `sources`

**Cuando** `upsert_document` guarda sus segmentos

**Entonces** la proyección crea `knowledge_sources` usando el `video_id` y URL
del segmento.
