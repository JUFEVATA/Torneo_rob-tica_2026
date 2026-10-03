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
| **N5** | Indicador de actualización automática |

Cambia la cantidad directamente. **F5 = 4** genera cuatro bloques; **F5 = 8** genera ocho. No hay casilla adicional. Por ejemplo, 54 equipos y 8 grupos se distribuyen **7/7/7/7/7/7/6/6** al siguiente refresco.

Al reducir el total se mantienen los primeros nombres de la lista y los demás pasan a **Reserva**, conservando sus identificadores. Al aumentarlo se reincorporan primero esos nombres; si hacen falta más, se añaden **Equipo nuevo 1…** para que los renombres en las tarjetas. La hoja interna Reserva está oculta y el administrador puede consultar esos nombres en Equipos. No se borran nombres al reducir la cantidad.

La cantidad de grupos puede cambiar incluso con clasificaciones: los nombres, estados y rondas se conservan. La cantidad de equipos y los cupos solo pueden cambiar antes de marcar resultados. Al reducir el total por debajo de los cupos, estos se ajustan a la mayor potencia de dos que cabe. La nueva distribución se guarda; refrescar no vuelve a sortear. Para iniciar sesión, pulsa discretamente **EQUIPO STEM 2026** bajo el título de la barra lateral e introduce la contraseña. El administrador dispone de estos controles en Configuración.

Los desplegables ofrecen cantidades habituales; también puedes escribir un entero hasta 4096. Los cupos admitidos son 2, 4, 8, 16, 32 o 64. No pueden superar los equipos inscritos.

### Introducir participantes y avanzar

1. En Grupos, introduce el listado con el formato del [ejemplo de 85 equipos](examples/sumo2026.txt). Para importar una lista completa, entra a editar **A1** (doble clic) y pega todo el texto dentro de esa única celda. No pegues sobre varias tarjetas. La app lo organiza en tarjetas y añade los desplegables al sincronizar. Conserva el encabezado `Competencia: Sumo` y las secciones `Equipo 1`, `Equipo 2`… También puedes importar desde **Competencia → Configuración → Importar una lista con grupos ya asignados** como administrador.
2. El grupo original se conserva: no se vuelve a sortear. Los 85 equipos del ejemplo están repartidos **22 / 21 / 21 / 21**. Todos empiezan Pendiente; se configuran **32 cupos** para dieciseisavos. Nuevas listas usan la mayor potencia de dos posible, hasta 32; el administrador puede modificar los cupos antes de iniciar eliminatorias.
3. Marca **Clasifica** junto a cualquier equipo. Aparece en **16 avos** al sincronizar, sin esperar a resolver todos los grupos.
4. En cada ronda eliges libremente **Clasifica**, **No clasifica** o **Pendiente**. No hay parejas obligatorias ni perdedores automáticos. Cada seleccionado aparece en la siguiente hoja.
5. Capacidades máximas: grupos → 32, dieciseisavos → 16, octavos → 8, cuartos → 4, semifinal → 2 y final → 1 campeón. Puedes ir completando las selecciones; no necesitas llenar una ronda para ver avanzar sus clasificados.
6. **Inicio** muestra los participantes y estados de la etapa publicada. El administrador puede consultar **Historial** para filtrar y descargar todas las decisiones por fase.

Mantén abierta la aplicación Streamlit para procesar las ediciones de Sheets. La vista pública consulta los cambios cada 10 segundos; por la caché pueden tardar aproximadamente **10–20 segundos**. **Actualizar datos** fuerza la lectura. No hay un proceso programado que avance el torneo si la aplicación está cerrada o suspendida.

### Edición y correcciones

- Edita nombres y desplegables en las hojas visibles. No alteres las columnas ocultas de IDs ni las pestañas internas.
- Puedes corregir estados directamente en Sheets o desde la interfaz de administrador. Si retiras una clasificación, ese equipo sale de las fases posteriores y se descartan sus decisiones posteriores; los demás conservan sus resultados.
- Una ronda que excede los cupos queda pendiente de corrección y conserva las selecciones escritas. El administrador ve el motivo. Las otras rondas y el selector de grupos pueden seguir sincronizándose.
- Una lista incompleta, nombres duplicados o IDs modificados no sobrescribe el último torneo válido. Corrige la entrada antes de continuar.
- Para una nueva competencia utiliza un nombre diferente e importa desde Configuración. No borres bloques de otras competencias.
- Los torneos requieren al menos dos equipos. Los cupos admitidos son 2, 4, 8, 16, 32 o 64, sin pases libres. Con 64 cupos aparece también **32 avos**.

## Seguidor de línea por tiempos

En **Competencia → Configuración → Crear una competencia**, elige explícitamente **Seguidor de línea por tiempos**. Configura el total de equipos y grupos y pulsa **Crear competencia y grupos**. Puedes pegar nombres o dejar que se creen equipos editables. En esa misma acción se preparan los grupos, la primera fase y las cuatro hojas de tiempos; la nueva competencia queda seleccionada. Las tarjetas de Grupos sirven para organizar y editar la inscripción; la clasificación de esta modalidad se obtiene de los tiempos.

Reglas del reglamento aportado, versión 2 septiembre 2026:

- Cuatro fases: participan todos; avanzan los 16 mejores, después los 8 y luego los 4. Los tres mejores tiempos válidos de la cuarta fase definen el podio.
- Tres intentos por equipo en cada fase. Se conserva el menor tiempo válido de esa fase; los tiempos anteriores no se suman.
- Máximo **90 segundos** por recorrido. Cada intento y el mejor tiempo tienen tres columnas numéricas: **MM (minutos), SS (segundos), MS (milisegundos)**. Por ejemplo, `01 | 02 | 345`. La aplicación compara milisegundos enteros; Sheets nunca los interpreta como horas del día.
- **Tres fallos nuevos en cada fase**, según la aclaración del organizador. El juez registra cuántos fallos penaliza; al llegar a tres, el equipo queda descalificado de esa fase. Un intento fallido y el contador de fallos son campos separados para registrar la decisión del juez sin inventar segundos de sanción.
- Máximo dos integrantes por equipo y un robot. La presentación del robot, la intervención, el tiempo de reparación (un minuto) y la espera de salida (dos segundos) se controlan en pista por el juez; la app no añade esos segundos a los recorridos.
- Los empates que afectan el último cupo o los puestos del podio requieren **órdenes de desempate diferentes** asignados por el juez. El nombre del equipo no decide una clasificación.

Como administrador, abre **Registro de tiempos**, selecciona fase y equipo, y captura por separado minutos, segundos y milisegundos para los tres intentos. También puedes indicar **No terminó**, **Fallo**, **No presentó** o una descalificación. Guarda los tiempos y, cuando todos tengan sus tres intentos o una decisión del juez, confirma **Cerrar fase y clasificar**.

En el mismo Google Sheet aparecen **SL Fase 1**, **SL Fase 2**, **SL Fase 3** y **SL Final**. Cada intento tiene un encabezado agrupado y tres columnas MM, SS y MS; completa las tres, incluidos los ceros. Usa 0–59 para minutos y segundos, y 0–999 para milisegundos. Las tres celdas vacías representan un intento pendiente. En Resultado intento 1–3 puedes seleccionar Fallo, No terminó o No presentó. Edita también el contador Fallos, Sanción y el orden de desempate. Los bloques de intentos tienen colores suaves distintos y se muestran N.º, Grupo y Equipo. Selecciona **Cerrada** junto a **Estado de fase** para avanzar. Las tres columnas de Mejor tiempo, Puesto y Estado los calcula la aplicación; no los edites. Las columnas ocultas conservan la identidad de cada equipo. La hoja **Podio** muestra automáticamente los tres puestos cuando se cierra la final; los jueces pueden corregirlos manualmente.

Puedes corregir cualquier fase anterior. Se recalculan los clasificados, se conservan los tiempos de quienes siguen participando y se retiran las decisiones que dependían de equipos que salen. Si un nuevo clasificado todavía no tiene sus intentos, la fase posterior vuelve a quedar abierta. Las entradas inválidas permanecen en su hoja para corregirlas y no bloquean las otras hojas.

En público, **Inicio** muestra la fase publicada y sus mejores tiempos; **Fases** presenta las cuatro etapas y permite consultar sus participantes; **Podio** muestra las medallas. No hay descargas públicas.

## Recuperación forzada

Entra como administrador y abre **Competencia → Administración → Eliminar o reiniciar competencia**. Esta sección también está disponible en el mensaje de error si los datos internos impiden cargar el torneo.

Selecciona el torneo y la acción, escribe su nombre exacto, marca la confirmación y pulsa **Aplicar acción**:

- **Eliminar** retira la competencia y sus hojas visibles. Si sus datos pueden leerse, también se conservan en Papelera.
- **Reiniciar resultados** conserva nombres, IDs y grupos; limpia clasificaciones, partidos, tiempos, cierres y podio.
- **Reiniciar fase actual** limpia los resultados de la etapa activa y las que dependen de ella. **Reiniciar eliminatorias** conserva la fase inicial.
- **Reiniciar competencia** limpia equipos y resultados y deja una configuración nueva utilizable. Si una configuración no se puede leer, se usa una configuración inicial de 32 equipos que puedes modificar.

Siempre se conserva un respaldo de las entradas anteriores en la hoja interna **Recuperaciones**, descargable desde **Respaldos de recuperación**. Se conservan las demás competencias y sus entradas manuales pendientes. Las escrituras comprueban si hubo una edición concurrente antes de guardar; si los datos cambiaron, actualiza y vuelve a intentar. La recuperación no sustituye las correcciones normales: puedes cambiar nombres o clasificaciones anteriores sin reiniciar todo.

## Modo público y administrador

El público ve únicamente **Inicio**, **Fases** y **Podio**. No puede elegir la competencia. **Inicio** muestra la etapa publicada y sus participantes; Grupos conserva sus tarjetas y cada ronda posterior reúne todos los participantes en un único panel de columnas adaptables, sin dividir la ronda en bloques numerados ni ofrecer descargas CSV públicas. Los nombres visibles son 16avos de final, Octavos de final, Cuartos de final, Semifinal y Final. **Fases** presenta un árbol simétrico con el campeón al centro, rondas pendientes y estados de los equipos. Puedes ampliar los nombres o ver el árbol desde otra ronda; en clasificación libre sus líneas conectan etapas y no definen rivales.

Para iniciar sesión, pulsa discretamente **EQUIPO STEM 2026** bajo el título de la barra lateral e introduce la contraseña. El menú del administrador reúne la gestión en **Competencia** (Configuración, Equipos, Publicación y Administración), **Resultados** (Grupos y Eliminatorias) o **Registro de tiempos**, e **Historial**, además de las tres vistas públicas. La configuración se guarda con un único botón y las acciones de eliminación o reinicio están en un único formulario con respaldo. Las operaciones de escritura comprueban la autenticación en el servidor. Al cerrar sesión se retiran los controles de gestión y el selector de competencia.

### Elegir qué ve el público

1. Entra como administrador y abre **Competencia → Publicación**.
2. Selecciona **Competencia para el público**. Esa elección se comparte con todos los visitantes y se conserva al reiniciar.
3. En **Etapa visible en Inicio**, deja **Automática según clasificaciones**, o selecciona manualmente una etapa.
4. Pulsa **Publicar competencia y etapa**. Elegir una etapa manual cambia la presentación sin modificar clasificaciones ni resultados.

### Primer, segundo y tercer puesto

Como administrador, abre **Podio** y elige los tres equipos en **Editar puestos → Guardar podio**. También puedes usar la hoja visible **Podio** de Google Sheets: incluye tres filas por competencia y un desplegable en **Equipo** para asignar cada puesto. Los cambios se sincronizan en ambos sentidos, sin modificar la clasificación de las rondas. Conserva los encabezados y las filas; para quitar una asignación, selecciona **Por definir**. Los visitantes ven únicamente el resultado. Un equipo no puede ocupar dos puestos. Los puestos pueden quedar **Por definir**. Si no se asigna manualmente el primero, se muestra el campeón de la final cuando existe; en torneos por parejas, también se obtiene automáticamente el segundo. Los puestos manuales se guardan por identidad del equipo y no cambian su clasificación deportiva.

### Eliminar una competencia creada por error

Selecciona la competencia como administrador y entra a **Competencia → Administración → Eliminar o reiniciar competencia**. Elige **Eliminar**, escribe el nombre exacto, confirma la acción y pulsa **Aplicar acción**. Sale de la aplicación y de las hojas visibles; sus datos se guardan en la **Papelera**. Desde **Competencia → Administración → Papelera → Restaurar competencia** recuperas configuración, equipos y resultados. Si eliminaste todas, Administración sigue disponible. La restauración no puede sobrescribir una competencia activa con el mismo nombre.

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

Las hojas visibles son entradas editables y vistas de cada ronda. Las hojas ocultas **Configuracion**, **Equipos**, **Reserva**, **Partidos**, **Rondas**, **Clasificados**, **Resultados**, **Publicacion** y **Papelera** conservan identidades estables, configuración y resultados. No las elimines. Ocultar una hoja sirve para simplificar la interfaz; no es un control de acceso.

El repositorio lee todas las tablas en un `values_batch_get`, valida las ediciones y escribe los datos relacionados y desplegables en un solo `spreadsheets.batchUpdate`. Antes de guardar compara una huella y vuelve a leer para detectar ediciones simultáneas. No escribe al refrescar si nada cambió. Los nombres se envían como texto, incluso si empiezan por `=`.

Un bloqueo compartido serializa las sesiones del mismo proceso. La API de Sheets no ofrece una transacción con compare-and-swap entre lectura y escritura: usa **un único despliegue escritor** y coordina las ediciones manuales para evitar cambios justo durante un guardado. Si aparece un conflicto, actualiza y repite la operación. Si una escritura no se confirma, comprueba el estado antes de repetirla.

Código principal:

- `core/group_board.py`: tarjetas, controles automáticos de cantidades, distribución y reserva.
- `core/sheet_flow.py`: importación del boletín, decisiones por hoja, participantes actuales e historial.
- `core/publication.py` y `core/tree.py`: competencia pública, etapa manual, podio, papelera y árbol visual.
- `core/free_rounds.py`: clasificación libre y propagación por identidad estable.
- `core/tournament.py` y `core/eliminatorias.py`: validaciones, distribución y avance de rondas.
- `services/google_sheets.py`: sincronización, escritura por lote y desplegables.
- `services/runtime.py`: autenticación, caché y manejo de conflictos.
- `components/`: vistas públicas y formularios del administrador.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

Las pruebas usan datos temporales, sin credenciales. Verifican distribución, listas en una celda o varias filas, cupos, rondas completas, correcciones, concurrencia, persistencia y acceso público/administrador con Streamlit AppTest. GitHub Actions ejecuta la suite en Python 3.12, 3.13 y 3.14. Consulta `VERIFICACION.md` para los resultados de esta entrega.
