# Plugins de resolución

`acquire.py pending` resuelve cada fila del catálogo por una cadena de
resolvers: primero los built-ins (`direct` para URLs explícitas,
`open-library` como hint de búsqueda) y luego los **plugins** de tu
instalación.

Un plugin es un `.py` en `$FOUNDER_GUIDE_RESOLVER_DIR`
(default `~/.config/founder-guide/resolvers/`) que define:

```python
def resolve(row) -> Iterable[Candidate | dict]
```

`row` llega como `{columna: valor}` del catálogo (`HEAD` en
`scripts/resolvers.py`). Devuelve candidatos; `direct=True` los hace
descargables por `acquire.py add`, `direct=False` quedan como hints para el
paso humano.

## Instalar el ejemplo

```sh
mkdir -p ~/.config/founder-guide/resolvers
cp plugins/libgen.py ~/.config/founder-guide/resolvers/
acquire.py pending    # ahora las filas sin URL muestran el link de búsqueda
```

Los plugins viven fuera del repo a propósito: cada instalación decide qué
fuentes resuelve, y resolvers más agresivos (descargas automáticas, sitios
grises) no necesitan estar versionados ni compartidos.
