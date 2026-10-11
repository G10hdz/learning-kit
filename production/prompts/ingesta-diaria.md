# Prompt maestro de ingesta diaria

## Variables

- `FECHA`
- `CATEGORIA`
- `NIVEL`
- `CONCEPTO`
- `RUTA_RESUMEN`
- `RUTA_LOG`
- `RUTA_SALIDA`

## Selección de tema

1. La sesión puede ser mono-tema o mezclar categorías cuando el tema lo pida (ej. "negociación aplicada a system design"). La rotación VC → Institucional → Ivy → Cultural es el default, no una jaula; si mezclas, decláralo en el título y en el log.
2. Candidatas: entradas del catálogo (`vault/sources/_catalogo.md`) de la categoría del día que no figuren como estudiadas en el log.
3. Si alguna tiene `impact_score`, prefiere la de mayor score; empate o todas vacías → mantiene la rotación.
4. El score no sustituye el criterio: si el de mayor score no sirve para el nivel actual, toma el siguiente y anótalo en el log.

## Prompt

Actúa como arquitecto de aprendizaje y editor técnico. Trabaja únicamente con el resumen indicado y el historial de estudio. No inventes tesis, citas ni datos ausentes.

1. Lee `RUTA_LOG` para evitar repetir contenido y detectar el siguiente hueco de comprensión.
2. Lee `RUTA_RESUMEN`, extraído de NotebookLM, y conserva la procedencia de cada afirmación.
3. Copia `templates/daily-brief.tex` a `RUTA_SALIDA/FECHA-CONCEPTO.tex` y sustituye sus marcadores sin reescribir el preámbulo. Apunta a dos a cuatro páginas densas; no fuerces saltos ni texto de relleno.
4. Si `pdflatex` está disponible, compila el PDF y elimina únicamente los auxiliares generados por esa compilación.
5. Añade una fila a `RUTA_LOG` con el tema, rutas de entrada y salida, comprensión observada y siguiente paso.
6. Genera los artefactos de ingesta junto al `.tex`:
   - `FECHA-TEMA-links.md`: lista plana de URLs citadas en el brief (una por línea, encabezado `### 🔗 NotebookLM Ingestion Links`).
   - `FECHA-TEMA-manifest.json`: schema 1.0 con `date`, `category`, `topic`, `notebook.suggested_title`/`description`/`notebook_url` (vacío hasta crear la libreta), `sources[]` (type/url/title/note, solo las citadas) y `audio_overview` (generate/language/custom_prompt en español resumiendo el hilo del día).

El documento debe conservar la paleta, tipografía, encabezados, tarjetas de fuente, cajas y ejercicios de la plantilla. Organiza el contenido con `\partdivider` en estas dos partes:

### Parte I: Anatomía del Concepto

- Definición operativa.
- Tesis central y mecanismo causal.
- Vocabulario imprescindible.
- Actores, incentivos y tensiones.
- Un ejemplo y un contraejemplo.
- Límites, críticas o incertidumbres.

### Parte II: Simulador de Señalización

- Tres contextos de conversación distintos.
- Para cada contexto: apertura honesta, pregunta útil, posible respuesta y seguimiento.
- Un caso de estudio con decisión y trade-offs.
- Dos errores que revelarían comprensión superficial.
- Un ejercicio de recuperación sin notas y su solucionario.

Cierra con `Fuentes y citas`. Incluye únicamente referencias verificadas en el resumen normalizado, con DOI o URL cuando exista.

No uses frases para fingir dominio. Prefiere “estoy estudiando…”, “mi lectura provisional es…” y preguntas que permitan corregir el modelo mental. Devuelve al final las rutas creadas y cualquier dato marcado como `PENDIENTE`.
