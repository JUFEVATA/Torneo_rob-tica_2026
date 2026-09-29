# Torneos de robótica · Equipo STEM 2026

Aplicación Python/Streamlit conectada a Google Sheets. El libro conserva los equipos, grupos y resultados; GitHub contiene el código. Paleta proporcionada para EPM: `#0D9648`, `#9FCF67`, `#45AD49`, `#00A99D`, `#0087C3` y blanco.

## Uso del torneo

La primera pestaña visible del libro es **Grupos**, organizada en tarjetas **Equipo 1, Equipo 2…**, hasta seis por fila, con colores EPM. Cada equipo tiene un desplegable con **Pendiente**, **Clasifica** y **No clasifica**. Las siguientes pestañas son **16 avos**, **8vos**, **4tos**, **Semifinal** y **Final**. Se conserva cada fase anterior como historial.

### Seleccionar cantidades desde la hoja

En el primer torneo, la fila 5 contiene los controles:

| Celda | Control |
|---|---|
| **B5** | Equipos inscritos que estarán en competencia |
| **F5** | Cantidad de bloques / grupos |
| **J5** | Cupos que clasifican a eliminatorias |
| **N5** | Casilla **Aplicar cambios** |

Selecciona las cantidades y marca **N5**. Por ejemplo, **54 equipos y 8 grupos** producen **7/7/7/7/7/7/6/6**. La casilla vuelve a desmarcarse al guardar. Modificar un selector por separado solo deja un borrador; los grupos siguen intactos hasta aplicar.

Al reducir el total se mantienen los primeros nombres de la lista y los demás pasan a **Reserva**, conservando sus identificadores. Al aumentarlo se reincorporan primero esos nombres; si hacen falta más, se añaden **Equipo nuevo 1…** para que los renombres en las tarjetas. La hoja interna Reserva está oculta y el administrador puede consultar esos nombres en Equipos. No se borran nombres al reducir la cantidad.

La aplicación solo permite redistribuir con todos los estados en **Pendiente**, antes de las eliminatorias. Cuando ya hay clasificaciones, los controles muestran **Distribución cerrada / Bloqueado** y dejan de ser desplegables; no se borran resultados para habilitarlos. Los grupos quedan equilibrados y se guardan; refrescar no vuelve a repartirlos. Desde **Configuración → Cantidad de equipos y grupos** el administrador dispone de los mismos controles y puede elegir sorteo aleatorio. Para recuperar exactamente una distribución anterior después de aplicar otra, usa un respaldo: aumentar la cantidad restaura nombres, pero calcula grupos de nuevo.

Los desplegables ofrecen cantidades habituales; también puedes escribir un entero hasta 4096. Los cupos admitidos son 2, 4, 8, 16, 32 o 64. No pueden superar los equipos inscritos.

### Introducir participantes y avanzar

1. En Grupos, introduce el listado con el formato del [ejemplo de 85 equipos](examples/sumo2026.txt). Para importar una lista completa, entra a editar **A1** (doble clic) y pega todo el texto dentro de esa única celda. No pegues sobre varias tarjetas. La app lo organiza en tarjetas y añade los desplegables al sincronizar. Conserva el encabezado `Competencia: Sumo` y las secciones `Equipo 1`, `Equipo 2`… También puedes importar desde **Configuración → Importar lista de grupos** como administrador.
2. El grupo original se conserva: no se vuelve a sortear. Los 85 equipos del ejemplo están repartidos **22 / 21 / 21 / 21**. Todos empiezan Pendiente; se configuran **32 cupos** para dieciseisavos. Nuevas listas usan la mayor potencia de dos posible, hasta 32; el administrador puede modificar los cupos antes de iniciar eliminatorias.
3. Marca el estado al lado de cada equipo. Al decidir todos los estados y tener exactamente 32 clasificados, se crean los 16 partidos de **16 avos**. Si quedan decisiones pendientes, los grupos continúan abiertos. El administrador también puede iniciar explícitamente el cuadro desde **Clasificados** al completar los cupos.
4. En cada ronda hay dos filas por partido. Selecciona **Clasifica** para el ganador; su rival pasa automáticamente a **No clasifica**. También puedes señalar al perdedor. No marques a ambos como ganadores o como perdedores.
5. Al terminar todos los partidos de una ronda, se llena la siguiente: **32 → 16 → 8 → 4 → 2 → campeón**. Las hojas todavía no alcanzadas muestran solo su encabezado.
6. **Participantes actuales** muestra quienes siguen compitiendo. **Historial** conserva la clasificación de grupos y los resultados por fase; permite filtrar y descargar CSV.

Mantén abierta la aplicación Streamlit para procesar las ediciones de Sheets. La vista pública consulta los cambios cada 10 segundos; por la caché pueden tardar aproximadamente **10–20 segundos**. **Actualizar datos** fuerza la lectura. No hay un proceso programado que avance el torneo si la aplicación está cerrada o suspendida.

### Edición y correcciones

- Edita nombres y desplegables en las hojas visibles. No alteres las columnas ocultas de IDs ni las pestañas internas.
- Durante las eliminatorias, la clasificación de grupos queda cerrada. Para modificarla, un administrador debe reiniciar las eliminatorias con confirmación.
- Para cambiar un ganador ya guardado, usa **Eliminatorias → Corregir resultado** y confirma. Se anulan los resultados posteriores afectados; las demás ramas se conservan. Si intentaste cambiarlo directamente en Sheets, restaura primero su estado anterior para que la lectura vuelva a ser válida.
- Una lista incompleta, nombres duplicados, grupos desequilibrados o resultados incompatibles quedan pendientes de revisión. La vista pública conserva los últimos resultados válidos; el administrador ve el motivo. Corrige la hoja antes de guardar otras operaciones: la app no borra las selecciones incompatibles ni guarda una importación parcial.
- Para una nueva competencia utiliza un nombre diferente e importa desde Configuración. No borres bloques de otras competencias.
- Los torneos requieren al menos dos equipos. Los cupos admitidos son 2, 4, 8, 16, 32 o 64, sin pases libres. Con 64 cupos aparece también **32 avos**.

## Modo público y administrador

El público ve Inicio, Participantes actuales, Historial, Grupos, Clasificados, Eliminatorias, Cuadro y Resultados. **Configuración, Equipos y Administración solo aparecen al iniciar sesión como administrador.** Las operaciones de escritura de la interfaz vuelven a comprobar la autenticación en el servidor.

La contraseña procede exclusivamente de `st.secrets["admin"]["password"]`. No hay una contraseña incorporada al código. Los permisos de edición del Google Sheet son independientes de la contraseña de Streamlit: comparte el libro solo con quienes deban administrarlo.

## Ejecutar localmente

Python 3.12 o posterior:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Sin Secrets aparece el botón de demostración. También puedes usar `ROBOTICA_DEMO=1 streamlit run app.py`. La demo tiene datos ficticios separados en `.demo/torneo.json`; no escribe ni importa automáticamente al libro real. No uses ese modo para producción.

## Google Sheets y Secrets

1. Habilita **Google Sheets API** en tu proyecto de Google Cloud.
2. Crea una cuenta de servicio y descarga su clave JSON. No necesita un rol de administrador del proyecto.
3. Comparte tu Google Sheet con el `client_email` del JSON como **Editor**. No hace falta publicar el libro ni habilitar Drive API.
4. Copia el ID del enlace: `https://docs.google.com/spreadsheets/d/ID/edit`.
5. Usa [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example) para crear `.streamlit/secrets.toml` localmente. En Streamlit Cloud pega ese contenido en **Secrets**.

```toml
[google_sheet]
sheet_id = "ID_DEL_GOOGLE_SHEET"

[admin]
password = "TU_CONTRASENA"

[gcp_service_account]
type = "service_account"
project_id = "PROYECTO"
private_key_id = "VALOR_DEL_JSON"
private_key = """-----BEGIN PRIVATE KEY-----
CONTENIDO_REAL_DEL_JSON
-----END PRIVATE KEY-----
"""
client_email = "CUENTA@PROYECTO.iam.gserviceaccount.com"
client_id = "VALOR_DEL_JSON"
token_uri = "https://oauth2.googleapis.com/token"
```

No subas el JSON ni el TOML real a GitHub. La configuración pública de colores sí está en `.streamlit/config.toml`. Tras cambiar credenciales, reinicia la aplicación para renovar la conexión.

## Despliegue

En Streamlit Community Cloud selecciona el repositorio, rama `main`, entrada `app.py` y Python 3.12 o posterior. Añade los Secrets y despliega. Las actualizaciones de código se publican en esa misma rama. El libro conserva los datos aunque se reinicie la aplicación.

## Persistencia y estructura

Las hojas visibles son entradas editables y vistas de cada ronda. Las hojas ocultas **Configuracion**, **Equipos**, **Reserva**, **Partidos**, **Clasificados** y **Resultados** conservan identidades estables, configuración y resultados. No las elimines. Ocultar una hoja sirve para simplificar la interfaz; no es un control de acceso.

El repositorio lee todas las tablas en un `values_batch_get`, valida las ediciones y escribe los datos relacionados y desplegables en un solo `spreadsheets.batchUpdate`. Antes de guardar compara una huella y vuelve a leer para detectar ediciones simultáneas. No escribe al refrescar si nada cambió. Los nombres se envían como texto, incluso si empiezan por `=`.

Un bloqueo compartido serializa las sesiones del mismo proceso. La API de Sheets no ofrece una transacción con compare-and-swap entre lectura y escritura: usa **un único despliegue escritor** y coordina las ediciones manuales para evitar cambios justo durante un guardado. Si aparece un conflicto, actualiza y repite la operación. Si una escritura no se confirma, comprueba el estado antes de repetirla.

Código principal:

- `core/group_board.py`: tarjetas, borradores de cantidades, distribución y reserva.
- `core/sheet_flow.py`: importación del boletín, decisiones por hoja, participantes actuales e historial.
- `core/tournament.py` y `core/eliminatorias.py`: validaciones, distribución y avance de rondas.
- `services/google_sheets.py`: sincronización, escritura por lote y desplegables.
- `services/runtime.py`: autenticación, caché y manejo de conflictos.
- `components/`: vistas públicas y formularios del administrador.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Las pruebas usan datos temporales, sin credenciales. Verifican distribución, listas en una celda o varias filas, cupos, rondas completas, correcciones, concurrencia, persistencia y acceso público/administrador con Streamlit AppTest. GitHub Actions ejecuta la suite en Python 3.12, 3.13 y 3.14. Consulta `VERIFICACION.md` para los resultados de esta entrega.
