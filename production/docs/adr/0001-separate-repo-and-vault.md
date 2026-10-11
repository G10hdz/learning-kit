# ADR 0001: Separar automatización y vault

## Estado

Aceptada.

## Contexto

El proyecto necesita código e instrucciones versionables, pero sus fuentes, notas y resultados son contenido personal sincronizado por Obsidian.

## Decisión

Mantener la automatización en un repo independiente bajo `~/projects` y el contenido en el vault. El repo accede al contenido mediante `CAPITAL_CULTURAL_VAULT` o el enlace local `./vault`, ignorado por Git.

## Consecuencias

El repo puede compartirse sin publicar la biblioteca personal. Cada máquina necesita configurar la ruta una vez. Los contratos de archivos son la única interfaz entre ambos lados.

## Alternativas consideradas

- Repo dentro del vault: mezcla historial técnico con PDFs y notas sincronizadas.
- Copiar contenido al repo: duplica archivos y crea conflictos de fuente de verdad.

