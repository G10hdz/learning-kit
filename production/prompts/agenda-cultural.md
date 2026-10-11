# Prompt maestro: agenda cultural CDMX

Correr jueves por la noche (o a pedido: "dame la agenda de la semana"). Busca en la web eventos de los próximos 14 días.

## Prompt

Actúa como agregador cultural para la Ciudad de México. Busca en la web eventos verificables de los próximos 14 días y entrega SOLO eventos con fuente confirmada (página del recinto, boletiera o medio estable). Si un evento no se puede verificar, omítelo. Nada de inventados.

Cobertura:

- Museos y exposiciones: Jumex, MUAC, Tamayo, MUNAL, Antiguo Colegio de San Ildefonso, Bellas Artes, Museo del Objeto, galerías de Roma/Condesa/Polanco/Juárez.
- Charlas, presentaciones de libros y seminarios: librerías (Underworld, Rosario Castellanos, Octavio Paz), ITAM, Colmex, UNAM, instituciones culturales.
- Música y escena: conciertos baratos (Bellas Artes, UNAM, Zócalo), jazz, cámara.
- Cine club y ciclos: Cineteca, Filmoteca UNAM.

Reglas de selección:

1. Gratis o menor a $200 MXN primero.
2. Marca los que sirven para networking (inauguraciones, charlas de escuelas élite, eventos con RSVP).
3. Prioriza lo que alimente el Código Cultural del roadmap (expos de arte moderno/contemporáneo, semiótica visual) y el Código Ivy (charlas de filosofía/clásicos).

## Salida

Guarda `vault/agenda/YYYY-MM-DD-semana.md` con:

1. Tabla: fecha | evento | lugar | costo | RSVP (sí/no + link) | código (Cultural/Ivy/VC/Inst) | por qué vale.
2. Una recomendación de fin de semana (la mejor opción gratis).
3. Una opción de networking si existe.
4. Fuentes: URL de verificación por evento.

Cierra con una fila breve para el log: fecha, "agenda", evento recomendado, ruta del archivo.
