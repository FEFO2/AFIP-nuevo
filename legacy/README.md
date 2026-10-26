# Archivos antiguos

`src/` reúne los diez accesos de compatibilidad que antes estaban en la carpeta
`src/` de la raíz. Importan la implementación actual de `bot_carga/`.
Los bots activos están en sus propias carpetas y no dependen de `legacy/`.

El inicio habitual del bot de carga es:

```powershell
python bot_carga/main.py --help
```

También funciona `python -m bot_carga`. Si una tarea programada o un acceso directo
usaba `src/main.py`, actualizarlo a `bot_carga/main.py`.

Los accesos archivados siguen funcionando desde su nueva ubicación; por ejemplo,
`python legacy/src/main.py --help`. No contienen otra copia del flujo de carga.
