# ADR-005: contrato unificado de fuentes y citas

## Estado

Aceptado.

## Contexto

El dominio actual usa `video_id`, URL y segundos en todas las capas. Libros,
markdown y notas necesitan páginas, paths o headings. Crear un pipeline por tipo
duplicaría búsqueda, respuesta y adaptadores.

## Decisión

Todos los tipos usan `Source -> Document -> Chunk`. `youtube`, `book`, `md` y
`note` solo cambian metadatos y locator. La búsqueda devuelve `Chunk`; la
respuesta solo puede citar los chunks recibidos.

Una cita tiene `chunk_id`, `source_id`, `source_type`, `title`, `uri` y un
locator discriminado:

- `timestamp`: `start_seconds` y `end_seconds`;
- `pages`: `page_start`, `page_end` y path;
- `heading`: path y heading.

`answer` es el caso de uso canónico y `q` es alias de CLI. HTTP y un MCP futuro
serializan el mismo resultado. La API v1 conserva `url` y `startSeconds` para
YouTube durante la migración.

`license` controla uso y exportación. `visibility_scope` controla quién puede
consultar. Son campos independientes y ambos se validan antes de recuperar.

## Consecuencias

- Un solo ranking y una sola regla de evidencia sirven para todas las fuentes.
- La migración de SQLite debe copiar datos viejos en tablas v2 dentro de una
  transacción y conservar las tablas v1 durante una versión.
- Los chunks de video y libro tienen políticas de tamaño distintas, sin falsos
  timestamps ni páginas inventadas.
- `Note` deja de ser un camino paralelo y pasa a ser `source_type=note`.

## Alternativas consideradas

- Columnas opcionales sobre los modelos actuales: descartado porque mantiene
  `video_id` como identidad universal.
- Un índice por tipo de fuente: descartado porque duplica consultas y citas.
