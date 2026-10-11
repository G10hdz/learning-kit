# Spec 100: búsqueda unificada de conocimiento

## Comportamiento

- La búsqueda consulta solo documentos activos de fuentes habilitadas.
- Una consulta vacía o sin coincidencias devuelve una lista vacía.
- Cada resultado incluye el contenido y una cita con fuente, URI y locator.
- Un scope de equipo puede leer contenido `shared` y contenido de su propio scope,
  pero nunca contenido de otro equipo.
- El ranking léxico favorece chunks que contienen más términos de la consulta.

## Fuera de alcance

- Embeddings, FTS y respuestas generadas.
- Exportación de contenido protegido.
