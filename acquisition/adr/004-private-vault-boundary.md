# ADR-004: vault privado separado del motor

## Estado

Aceptado.

## Contexto

`founder-guide` puede publicar el motor, pero el corpus incluye notas internas y
material comprado. Mezclar código y contenido vuelve fácil publicar archivos por
error y obliga a dar acceso al motor a quien solo necesita el conocimiento.

## Decisión

El motor permanece en `founder-guide`. El contenido vive en un repositorio
privado `team-vault`, montado por ruta local mediante `--vault` o `GUIDE_VAULT`.

El vault es la fuente editorial canónica para notas, documentos y snapshots de
fuentes permitidas. SQLite es una proyección local reconstruible. Los binarios
originales viven fuera de git en `_raw/`; el índice nunca se sincroniza al repo.

El contenido principal del vault será español. Identificadores, contratos y
términos técnicos pueden permanecer en inglés.

## Consecuencias

- Hay dos repositorios, pero no un servicio adicional.
- El motor puede seguir siendo público sin exponer el corpus.
- Cada cambio editorial se revisa en `team-vault`; cada cambio de comportamiento
  se revisa en `founder-guide`.
- `verify-corpus` debe detectar deriva y debe existir un rebuild desde el vault.
- Exportar contenido es fail-closed según licencia y visibilidad.

## Alternativas consideradas

- Guardar `vault/` en `founder-guide`: descartado por copyright y conocimiento
  interno.
- Usar PostgreSQL como verdad: descartado para el MVP porque dificulta edición,
  revisión en git y reconstrucción local.
