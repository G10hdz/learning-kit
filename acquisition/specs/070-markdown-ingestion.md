# SPEC-007: ingesta de Markdown

**Dado** un archivo Markdown legal y metadata explícita `book_id`, `section`,
`title`, `author` y `license`

**Cuando** se ingiere hacia un vault temporal

**Entonces** el vault contiene `section/book_id/_meta.yaml`, `full.md` y al
menos `chunks/001.md`; `full.md` conserva el contenido original y el chunk
tiene frontmatter con `source_type: book`, `book_id`, `section`, `title` y
`license`.

## SPEC-008: rutas confinadas al vault

**Dado** un `section` o `book_id` absoluto o con `..`

**Cuando** se intenta ingerir el Markdown

**Entonces** la operación falla antes de escribir fuera del vault.

## SPEC-009: reingesta idempotente

**Dado** un Markdown ya ingerido sin cambios de contenido o metadata

**Cuando** se ingiere por segunda vez

**Entonces** la operación reporta que no creó una nueva versión ni reescribe los
archivos derivados.
