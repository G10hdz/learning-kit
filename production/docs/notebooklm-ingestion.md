# Ingesta con Gemini Notebook

El proyecto usa `nlm` como adaptador. La instalación local verificada es `nlm 0.9.11`.

## Comprobación

```bash
nlm login --check
nlm doctor
```

## Crear una libreta

Usa una libreta por categoría para evitar mezclar vocabularios:

```bash
nlm notebook create "Capital Cultural - Código VC"
```

Guarda el ID devuelto en la columna `Notebook` de `vault/sources/_catalogo.md`.

## Añadir fuentes

```bash
nlm source add <notebook-id> --url "https://ejemplo.com/fuente.pdf" --wait
nlm source add <notebook-id> --file "/ruta/al/documento.pdf" --wait
nlm source list <notebook-id>
```

Lo que no tiene archivo ni URL queda como `pendiente_manual` en el catálogo.

## Extraer el resumen normalizado

```bash
nlm notebook query <notebook-id> "Resume exclusivamente las fuentes de esta libreta. Devuelve: tesis, conceptos, vocabulario, mecanismo causal, tensiones, ejemplos, citas verificables y dudas abiertas. Indica la fuente de cada afirmación." > vault/summaries/<categoria>/YYYY-MM-DD-<tema>.md
```

Revisa el archivo antes de generar el brief. Una respuesta sin procedencia no pasa a LaTeX.

## MCP

Un agente con `gemini-notebook-mcp` puede usar `notebook_create`, `source_add` y `notebook_query`. Debe producir los mismos archivos; el MCP no cambia los contratos del proyecto.

## Operación

- No compartas libretas públicamente por defecto.
- No guardes cookies, perfiles o credenciales dentro del vault.
- Si la API interna cambia, conserva el resumen local y usa carga manual hasta reparar el adaptador.
