# SPEC-013: rebuild del índice desde el vault

**Dado** un vault temporal que contiene `01-startup-negocio/mom-test/` con
`_meta.yaml`, `full.md` y `chunks/001.md`, creado por `ingest_markdown` sobre
`tests/fixtures/sample_book.md`

**Cuando** se llama `rebuild_index(vault, db_path)` de `founder_guide.index`
sobre una base SQLite v2 vacía

**Entonces** la base contiene exactamente:

- `knowledge_sources`: una fila con `source_id` = `book:mom-test`,
  `source_type` = `book`, `license` = `team-notes`, `canonical_uri` =
  `01-startup-negocio/mom-test/full.md` y `enabled` = 1.
- `knowledge_documents`: una fila activa (`active` = 1) con `source_id` =
  `book:mom-test`, `document_id` = `book:mom-test:{content_hash}`,
  `content_hash` = SHA-256 en hex de `full.md`, `language` = `es`,
  `canonical_path` = `01-startup-negocio/mom-test/full.md` y `version` = 1.
- `knowledge_chunks`: una fila por archivo en `chunks/` con `content` sin el
  frontmatter del archivo, `locator_kind` = `heading`, `path` =
  `01-startup-negocio/mom-test/chunks/001.md` y `document_id` que referencia
  al documento anterior.

## SPEC-014: rebuild determinista sobre bases vacías

**Dado** el mismo vault ingerido dos veces en vaults temporales distintos

**Cuando** se corre `rebuild_index` hacia dos bases SQLite v2 vacías
diferentes

**Entonces** ambas bases tienen los mismos `source_id`, `document_id` y
`chunk_id` en sus filas de conocimiento.

## SPEC-015: una sola versión activa

**Dado** un libro ya indexado cuyo contenido cambia

**Cuando** se ingiere y reconstruye el índice sobre la misma base

**Entonces** se conserva la versión anterior, pero solo el documento del hash
nuevo queda activo y las versiones son consecutivas.

## SPEC-016: directorios internos no se indexan

**Dado** contenido con forma de libro bajo `_raw/` o `_export/`

**Cuando** se reconstruye el índice

**Entonces** esos directorios se ignoran aunque contengan `_meta.yaml` y chunks
válidos.
