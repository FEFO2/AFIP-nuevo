# Seguridad y credenciales

## Accesos que ya estaban en Git

La revisión de esta rama encontró `.env` versionado y credenciales incrustadas en
scripts y documentación antiguos. También había facturas y datos de clientes.
Que el repositorio sea privado no convierte esos valores en seguros.

Cambiar las contraseñas de **AFIP/ARCA, Arancia/Bookit y PGA/Newsan**, revisar las
sesiones abiertas y revocar las que correspondan. Si una contraseña se reutilizó
en otro servicio, cambiarla allí también. Actualizar después el `.env` local.
Los nombres de usuario no se renuevan necesariamente; las contraseñas sí.

Los archivos OAuth de Gmail presentes localmente quedaron excluidos del nuevo
commit. Si se compartieron por otra vía insegura, revocar esos tokens y volver a
autorizar la cuenta. No se han usado las credenciales ni cambiado accesos durante
esta limpieza.

Este commit retira secretos y documentos de la versión actual, pero **no borra
los commits antiguos ni las demás ramas**. No se ha reescrito el historial ni
forzado ningún push. Si se necesita eliminar ese material de todo el historial,
coordinar una limpieza de todas las referencias, los clones y las copias con
acceso, después de rotar las claves. Un clon de esta rama todavía hereda el
historial antiguo; no debe compartirse públicamente.

## Prevención

- Guardar los accesos en `.env` o variables del sistema; `.env.example` solo lleva
  nombres y valores vacíos.
- Los bots cargan el `.env` de la raíz del proyecto sin sustituir variables del
  sistema. Los errores de configuración solo muestran el nombre que falta.
- No versionar facturas, adjuntos, exportaciones, tokens OAuth, estados de sesión,
  claves privadas, navegadores descargados ni entornos de Python.
- Instalar los controles con `python -m pre_commit install --install-hooks` en
  cada clon. El control de archivos privados detecta también `git add --force`.
- Gitleaks aplica sus reglas estándar y reglas adicionales para contraseñas
  incrustadas en campos Playwright. Los análisis usan salida censurada.
- GitHub Actions comprueba la versión actual; no ignora hallazgos nuevos usando
  una lista de secretos antiguos. El historial requiere un análisis separado.
- No publicar capturas, trazas del navegador ni logs de sesiones autenticadas.

Las comprobaciones reducen exposiciones accidentales; no garantizan detectar
todas las formas posibles de ocultar una clave. No usar `--no-verify` para saltar
un hallazgo: retirar el dato privado y repetir el control.

Referencias de las herramientas: [Gitleaks](https://github.com/gitleaks/gitleaks)
y [pip-audit](https://github.com/pypa/pip-audit).
