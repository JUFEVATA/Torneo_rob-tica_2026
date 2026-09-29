# Circuito · Torneos de robótica

Aplicación completa en Python y Streamlit para gestionar competencias independientes, equipos, grupos equilibrados y eliminatorias. Google Sheets conserva el torneo; GitHub almacena el código y Streamlit Community Cloud ejecuta la interfaz.

```text
GitHub → Streamlit Community Cloud ↔ Google Sheets API → Google Sheets
```

## Inicio rápido

Usa Python 3.12 o posterior. Las dependencias directas están fijadas en `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Sin credenciales se muestra una pantalla de conexión con **Explorar demostración**. La demostración pública contiene 32 equipos, 87 participantes y seis grupos. No escribe en Google Sheets. Para administrar la demo crea `.streamlit/secrets.toml` con solo:

```toml
[admin]
password = "REEMPLAZA_POR_UNA_CONTRASENA_PROPIA"
```

También puedes abrir directamente la demo:

```bash
ROBOTICA_DEMO=1 streamlit run app.py
# PowerShell: $env:ROBOTICA_DEMO="1"; streamlit run app.py
```

Sus datos persisten en `.demo/torneo.json`, ignorado por Git. **Este archivo es solo para demostración local**: no garantiza persistencia en Community Cloud. Producción siempre debe usar Google Sheets; no configures `ROBOTICA_DEMO` allí. Al conectar credenciales reales la demo no se migra automáticamente: el libro real comienza con sus propios datos.

## Funciones implementadas

- Nueve vistas: Inicio, Configuración, Equipos, Grupos, Clasificados, Eliminatorias, Cuadro, Resultados y Administración.
- Competencias separadas, con configuración, equipos, grupos, resultados y campeón propios.
- Alta, edición y eliminación de equipos; importación CSV UTF-8 con coma o punto y coma; pegado de listas; nombres genéricos. Duplicados detectados sin distinguir mayúsculas, espacios repetidos ni variantes Unicode equivalentes.
- Participantes por equipo y total esperado independientes. Se muestra el progreso registrado / esperado; no se presupone un tamaño uniforme.
- Distribución circular determinista o sorteo, ambos con cupos calculados por cociente y residuo. Grupos A…Z, AA, AB… y tarjetas adaptables.
- Clasificación con tres estados y límite de cupos. Bloqueo de eliminatorias hasta alcanzar la cantidad requerida.
- Cuadros de 2, 4, 8, 16, 32 o 64 clasificados, avance automático al terminar cada ronda y campeón persistente.
- Correcciones confirmadas: se actualizan los cruces afectados, se anulan sus resultados y se conservan los partidos de las ramas independientes.
- Reinicio de fase, eliminatorias o competencia, con casilla de confirmación y nombre exacto de la competencia.
- Modo público sin acciones de escritura, administrador autenticado con `st.secrets`, cierre de sesión y límite compartido de intentos de contraseña.
- Exportación CSV de equipos y resultados; nombres que parecen fórmulas se neutralizan al exportar y se escriben como texto en Sheets.
- Pruebas de dominio, persistencia, API simulada y flujos completos de interfaz con Streamlit AppTest.

Los torneos completos requieren al menos dos equipos. La función matemática `distribuir` también admite un solo equipo. La interfaz permite hasta 4096 equipos/grupos como límite operativo, aunque Sheets y una interfaz de tarjetas están pensados para torneos pequeños. Los **cupos de eliminatorias** se restringen a las seis potencias de dos indicadas: no hay pases libres ni fases de puntuación todos contra todos.

## Estructura del proyecto

```text
torneos-robotica/
├── app.py                         # Entrada Streamlit, navegación y vista pública
├── core/
│   ├── models.py                  # Configuración, equipos, partidos y competencias
│   ├── grupos.py                  # Distribución, sorteo y nombres estilo Excel
│   ├── eliminatorias.py           # Rondas, ganadores y propagación de correcciones
│   └── tournament.py              # Operaciones y validaciones del torneo
├── services/
│   ├── google_sheets.py           # gspread + google-auth, lecturas y commits por lote
│   ├── serialization.py           # Esquema de las seis pestañas
│   ├── repository.py              # Repositorio local transaccional para demo y tests
│   ├── runtime.py                 # Autenticación, caché y escrituras desde Streamlit
│   └── demo.py                    # Datos ficticios iniciales
├── components/
│   ├── layout.py                  # Tema, tarjetas, métricas y bracket HTML/CSS
│   ├── configuracion.py
│   ├── equipos.py
│   ├── grupos.py
│   ├── clasificados.py
│   ├── eliminatorias.py
│   └── admin.py
├── utils/helpers.py               # Importación y exportación CSV
├── tests/
│   ├── test_core.py
│   ├── test_persistence.py
│   └── test_app.py
├── .streamlit/
│   ├── config.toml                # Tema público, sin credenciales
│   └── secrets.toml.example        # Plantilla con datos falsos
├── .github/workflows/tests.yml     # CI en Python 3.12, 3.13 y 3.14
├── requirements.txt
├── .gitignore
├── VERIFICACION.md
└── README.md
```

Cada paquete incluye `__init__.py`. No se utiliza una base de datos adicional, una librería de brackets externa ni JavaScript personalizado. Las fuentes web tienen fuentes locales de respaldo.

## Configuración de Google Cloud y Google Sheets

1. **Crea un Google Sheet dedicado** al torneo. Puede estar vacío; la pestaña inicial predeterminada se deja intacta. Copia su URL.
2. En [Google Cloud Console](https://console.cloud.google.com/), crea o selecciona un proyecto.
3. En **APIs y servicios → Biblioteca**, busca **Google Sheets API** y habilítala. La aplicación abre el documento por ID y solicita únicamente el alcance `https://www.googleapis.com/auth/spreadsheets`; no necesita buscar archivos ni habilitar Drive API.
4. Ve a **IAM y administración → Cuentas de servicio → Crear cuenta de servicio**. Elige un nombre, por ejemplo `torneos-streamlit`. No necesita un rol de administrador del proyecto para acceder al libro compartido.
5. Abre esa cuenta → **Claves → Agregar clave → Crear clave nueva → JSON**. Descarga el archivo y consérvalo fuera del repositorio. Si tu organización prohíbe claves de cuentas de servicio, solicita el mecanismo autorizado a su administrador; no intentes desactivar esa política.
6. Copia `client_email` del JSON. Abre el Google Sheet → **Compartir** → añade ese correo como **Editor**. No es necesario publicar el documento ni compartirlo con todo Internet.
7. Obtén el ID de la URL: en `https://docs.google.com/spreadsheets/d/ESTE_ES_EL_ID/edit`, copia solo `ESTE_ES_EL_ID`.
8. Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml`, y sustituye los valores ficticios por los del JSON y el ID del libro.
9. Configura una contraseña de administrador propia en `[admin]`. El código no contiene una contraseña de acceso por defecto.
10. Ejecuta `streamlit run app.py` desde la raíz del proyecto. Al conectar se crean automáticamente las seis pestañas que falten.

La clave privada debe conservar sus saltos de línea dentro de una cadena TOML multilínea. Nunca pegues las credenciales en `app.py`, un issue, un README o un commit. El archivo real ya está excluido en `.gitignore`.

## Secrets locales y de Streamlit Cloud

La plantilla completa está en `.streamlit/secrets.toml.example`. Su estructura es:

```toml
[google_sheet]
sheet_id = "ID_DEL_GOOGLE_SHEET"

[admin]
password = "CONTRASENA_PROPIA"

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

La contraseña y las credenciales se leen exclusivamente de `st.secrets`. `session_state` solo mantiene la autenticación temporal, la selección de interfaz y los mensajes; nunca contiene la única copia del estado del torneo. Rotar la contraseña invalida las sesiones al volver a ejecutar la aplicación. Tras cambiar credenciales de Google reinicia la app para renovar el recurso de conexión cacheado.

## Estructura esperada de Google Sheets

Se utiliza **un único libro para todas las competencias**. Los nombres de competencia son únicos; no se renombran directamente en la hoja. Cada escritura de negocio actualiza las seis pestañas juntas.

### Configuracion

Columnas: `competencia | campo | valor`. La columna `competencia` separa las configuraciones; `campo | valor` sigue el modelo solicitado.

Campos de cada competencia:

```text
competencia
numero_equipos
numero_grupos
numero_participantes
cupos_clasificados
fase_actual
torneo_iniciado
equipos_por_grupo
campeon
metodo_grupos
```

Ejemplo parcial:

| competencia | campo | valor |
|---|---|---|
| Seguidor de línea | numero_equipos | 32 |
| Seguidor de línea | numero_grupos | 6 |
| Seguidor de línea | numero_participantes | 87 |
| Seguidor de línea | equipos_por_grupo | 6, 6, 5, 5, 5, 5 |
| Seguidor de línea | fase_actual | Grupos |
| Seguidor de línea | torneo_iniciado | TRUE |

`campeon` almacena el ID estable del equipo, no su nombre. `fase_actual` es Inscripción, Grupos, una ronda eliminatoria o Finalizado.

### Equipos

```text
id_equipo | nombre_equipo | competencia | grupo | clasificado | estado | numero_participantes
```

`grupo` almacena A, B…; `clasificado` es un booleano TRUE/FALSE; `estado` es Pendiente, Clasificado o Eliminado. Clasificado corresponde a TRUE; los otros dos estados a FALSE. El estado representa la decisión de grupos, no cada derrota posterior en eliminatorias. Los IDs son UUID persistentes: editar un nombre nunca rompe el bracket.

### Grupos

Cada grupo es una **columna**, incluso con cantidades desiguales. La fila 1 contiene `Grupo A`, `Grupo B`…; la fila 2 identifica la competencia; desde la fila 3 aparecen los nombres. Las columnas de cada competencia se ubican consecutivamente, sin mezclar equipos. Las dos primeras filas se congelan.

| Grupo A | Grupo B | Grupo C | Grupo A | Grupo B |
|---|---|---|---|---|
| Sumo | Sumo | Sumo | Edison | Edison |
| Equipo 1 | Equipo 2 | Equipo 3 | Robot 1 | Robot 2 |
| Equipo 4 | Equipo 5 | Equipo 6 | Robot 3 | Robot 4 |
| Equipo 7 | Equipo 8 | Equipo 9 | | |
| Equipo 10 | | | | |

La fila de competencia adicional permite almacenar todos los grupos en una sola pestaña y conservar los encabezados solicitados.

### Partidos

```text
id_partido | competencia | fase | numero_partido | equipo_1 | equipo_2 | ganador | estado
```

Se añaden `nombre_equipo_1 | nombre_equipo_2 | nombre_ganador` para lectura humana. `equipo_1`, `equipo_2` y `ganador` contienen IDs estables. La numeración de partidos comienza en 1 dentro de cada ronda. Estados: Pendiente, Finalizado y Por definir (cruces que quedan incompletos después de una corrección). Todas las fases comparten esta pestaña.

### Clasificados

```text
competencia | fase_destino | id_equipo | nombre_equipo | grupo
```

Vista calculada. Durante los grupos muestra los seleccionados para la primera ronda. Durante eliminatorias muestra los participantes que alcanzaron la ronda actual; al terminarla, se actualiza automáticamente con los ganadores que avanzan a la siguiente. La pantalla también muestra el avance parcial hacia la ronda siguiente. Al terminar muestra al campeón. La pantalla mantiene además el listado histórico de clasificados de grupos.

### Resultados

```text
competencia | posicion | id_equipo | nombre_equipo
```

Al finalizar, guarda permanentemente campeón (1) y subcampeón (2). Los resultados de todos los partidos siguen en Partidos. Una corrección que invalida la final elimina el podio hasta resolverla de nuevo.

### Edición manual permitida

- Puedes editar `nombre_equipo` y `numero_participantes` en Equipos, y `numero_participantes` en Configuracion.
- Antes de generar grupos puedes ajustar totales, grupos y cupos en Configuracion, respetando sus restricciones.
- Durante grupos, puedes cambiar `clasificado` y `estado` **juntos**, respetando el límite de cupos. Por ejemplo TRUE / Clasificado.
- Conserva encabezados, IDs y referencias. Usa la aplicación para ganadores, correcciones, reasignaciones, altas, bajas, reinicios y cambios de fase.
- No edites Grupos, Clasificados, Resultados ni las columnas de nombres de Partidos: son vistas calculadas que se reemplazan en la siguiente escritura. La interfaz calcula sus vistas desde los datos canónicos de Configuracion, Equipos y Partidos, por lo que los nombres corregidos se ven aun antes de regenerar esas pestañas.
- Evita modificar manualmente la hoja mientras hay administradores guardando. Si introduces una inconsistencia, la app muestra un error de validación y no sobrescribe los datos; corrígela en la hoja.
- No añadas información propia dentro de las seis pestañas gestionadas. Puedes usar otras pestañas del libro, que la aplicación no modifica.

## Uso durante un torneo

1. Accede mediante **Acceso administrador** en el menú lateral.
2. En **Configuración**, crea la competencia y define total de equipos, grupos, participantes y cupos.
3. En **Equipos**, registra equipos, pega una lista o importa un CSV. El CSV mínimo tiene encabezado `nombre_equipo`; `numero_participantes` es opcional. Puedes completar nombres genéricos.
4. En **Configuración**, selecciona orden original o sorteo y pulsa **GENERAR GRUPOS**. La operación valida y guarda configuración, equipos y grupos en un solo commit. El sorteo nunca ocurre en una lectura.
5. En **Grupos**, registra Clasifica / No clasifica / Pendiente. Puedes volver a Pendiente antes de generar eliminatorias.
6. En **Clasificados**, completa el contador exacto y genera eliminatorias por orden de inscripción o sorteo inicial. Los emparejamientos quedan guardados.
7. En **Eliminatorias**, elige el ganador de cada partido. Al cerrar una ronda, sus ganadores avanzan automáticamente: ganador 1 vs ganador 2, ganador 3 vs ganador 4… No se juega la siguiente fase con partidos previos pendientes.
8. Usa **Cuadro** para ver la progresión y **Resultados** para consultar o exportar. La vista pública actualiza cada 10 segundos mientras está abierta.
9. Para corregir un ganador ya elegido, abre **Corregir resultado**, elige el nuevo ganador o Quitar ganador y confirma. Si cambia un participante de un cruce posterior, ese cruce se debe volver a jugar aunque su ganador anterior siga presente.
10. Para reiniciar, ve a **Administración**. Reiniciar eliminatorias conserva la clasificación de grupos. Reiniciar la fase de grupos libera la estructura y conserva los nombres de equipos. Reiniciar la competencia elimina sus equipos y resultados, pero conserva la configuración para volver a empezar. Desde un torneo finalizado, reiniciar fase actual reabre la final.

Para cambiar grupos durante eliminatorias: primero reinicia Eliminatorias, después Fase actual (Grupos), modifica la configuración y genera grupos nuevamente.

## Persistencia, sincronización y concurrencia

- Google Sheets es la fuente de verdad. Una recarga, otra sesión, cerrar el navegador o reiniciar Streamlit no regenera sorteos ni elimina resultados de producción.
- Las lecturas obtienen las seis pestañas en **una petición `values_batch_get`**, sin consultas por equipo. `st.cache_data(ttl=10)` comparte los datos entre sesiones del mismo proceso.
- La vista pública usa `st.fragment(run_every="10s")`. Por la combinación de caché y temporizador, una edición puede tardar aproximadamente 10–20 segundos en verse; **Actualizar datos** fuerza lectura inmediata.
- El modo administrador no se refresca automáticamente mientras se rellenan formularios. Las interacciones vuelven a leer la caché y el botón de actualización obtiene datos nuevos. Antes de cada escritura siempre se relee Sheets sin caché.
- Cada formulario opera contra una huella del estado leído. Si otro administrador guardó antes, se rechaza la edición desactualizada, se actualiza la pantalla y se solicita repetirla.
- Un `RLock` compartido serializa lecturas/escrituras de las sesiones del proceso. Una segunda lectura previa al commit detecta cambios externos ocurridos durante el cálculo.
- Las seis pestañas se escriben con **un solo `spreadsheets.batchUpdate` de `updateCells`**. Google valida y aplica el lote atómicamente. Si falla una petición del lote, no se aplica parcialmente. Los rangos cubren también filas antiguas para que un reinicio no deje datos residuales.
- Después de guardar: invalidación de caché, relectura y rerun. Si la conexión falla después de enviar un commit, se muestra un estado incierto y no se repite automáticamente una escritura.

**Límite de Google Sheets:** la atomicidad del lote no es una transacción con compare-and-swap. No existe una garantía de exclusión entre la última lectura y la escritura frente a otro proceso/despliegue o un editor manual. Usa **un único despliegue escritor** para ese libro y coordina las ediciones manuales. Varios espectadores y administradores dentro del mismo proceso sí se serializan. Para varios escritores distribuidos con garantías estrictas se necesitaría un servicio transaccional adicional, fuera de la arquitectura solicitada.

Las peticiones se mantienen pequeñas para torneos escolares. No se cachean indefinidamente los datos ni se consultan resultados individualmente por equipo.

## Publicar en GitHub

Crea un repositorio vacío en tu cuenta y ejecuta desde esta carpeta:

```bash
git init
git add .
git status
# Revisa que no aparezcan secretos, claves ni .demo.
git commit -m "Aplicación de torneos de robótica con Streamlit y Google Sheets"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
git push -u origin main
```

Verifica la exclusión antes de subir:

```bash
git check-ignore .streamlit/secrets.toml
```

Si alguna clave se publicó por error, revócala en Google Cloud y genera otra; quitarla del commit más reciente no la elimina del historial ni restaura su seguridad.

## Desplegar en Streamlit Community Cloud

1. Publica el proyecto en GitHub, manteniendo `app.py` y `requirements.txt` en la raíz del repositorio.
2. Accede a [Streamlit Community Cloud](https://share.streamlit.io/) y conecta tu cuenta de GitHub.
3. Selecciona **Create app** y el repositorio, la rama `main` y el archivo de entrada `app.py`.
4. En **Advanced settings**, selecciona Python **3.12** (o una versión compatible con los requisitos).
5. En **Secrets**, pega el TOML real con `[google_sheet]`, `[admin]` y `[gcp_service_account]`. No subas el archivo real al repositorio.
6. Guarda y despliega. Comprueba que la página muestre los datos de Google Sheets y no el aviso de demostración.
7. Si es necesario, edita los Secrets posteriormente desde la configuración de la aplicación y reiníciala para renovar la conexión.
8. Inicia sesión como administrador, crea una competencia de prueba y completa la lista de comprobación de persistencia inferior antes del evento.
9. Comparte la URL pública de la aplicación. Los visitantes acceden en modo lectura; la contraseña habilita las modificaciones.

No es necesario publicar Google Sheets como documento público. Solo el Service Account necesita permiso de editor. La aplicación expone nombres de equipos y resultados en su modo público; no almacenes datos personales de integrantes en nombres de equipo.

## Pruebas y verificación de persistencia

```bash
python -m unittest discover -s tests -v
```

Se prueban todos los ejemplos obligatorios, propiedades de distribución para miles de combinaciones, grupos posteriores a Z, cuadros completos, correcciones de ramas, reinicios, duplicados, aislamiento, importación, escrituras obsoletas, atomicidad del lote simulado y flujos de administrador/público con AppTest.

Las pruebas locales usan un repositorio temporal y un doble de Google Sheets; no necesitan secretos ni modifican una hoja real. El workflow CI está preparado para Python 3.12, 3.13 y 3.14, pero los resultados ejecutados localmente se detallan en `VERIFICACION.md`.

**Comprobación de aceptación en tu Google Sheet real:**

1. Configura 32 equipos / 6 grupos. Genera un sorteo, anota al menos tres asignaciones y selecciona 32 cupos si quieres probar Dieciseisavos.
2. Clasifica los equipos y registra algunos ganadores. Comprueba las celdas correspondientes en Equipos y Partidos.
3. Pulsa F5: compara grupos, IDs de partidos y ganadores.
4. Cierra el navegador y vuelve a abrir la URL: deben permanecer iguales; el administrador deberá volver a autenticarse si perdió la sesión.
5. Reinicia Streamlit (localmente Ctrl+C y nuevo arranque, o reboot en Cloud): deben permanecer iguales.
6. Entra desde otro navegador o una ventana privada: el modo público debe mostrar el mismo torneo.
7. Cambia un nombre en Equipos desde Sheets; verifica la actualización pública en aproximadamente 10–20 segundos.
8. Con dos sesiones de administrador abiertas, intenta guardar formularios basados en el mismo estado: el segundo debe detectar el conflicto si el primero ya cambió los datos.
9. Completa 32 → 16 → 8 → 4 → 2 → campeón. Comprueba Resultados y el campo campeon en Configuracion.
10. Corrige un ganador temprano y verifica que desaparecen campeón y resultados descendientes afectados, mientras los partidos de otras ramas se conservan.

La conexión real, los permisos de tu cuenta y el despliegue requieren que configures tus propios Secrets. No están simulados como si ya hubieran sido verificados en tu infraestructura.

## Problemas habituales

| Síntoma | Qué revisar |
|---|---|
| Pantalla de conexión | Faltan secciones de Secrets; ejecútalo desde la raíz del proyecto. |
| No fue posible leer el torneo | ID incorrecto, Google Sheets API deshabilitada, clave inválida o documento no compartido como Editor con client_email. |
| Error al leer la clave | Conserva BEGIN/END PRIVATE KEY y saltos de línea en la cadena TOML. |
| Datos inválidos | Se alteraron encabezados, IDs, booleanos o estructura manualmente; consulta el esquema. |
| Conflicto al guardar | Otro usuario editó el libro. Revisa la pantalla actualizada y repite la operación. |
| Escritura no confirmada | Comprueba primero el estado actual; una respuesta perdida no demuestra que Google rechazó el cambio. |
| Los grupos no se regeneran | Es deliberado: reinicia la fase con confirmación para efectuar otro sorteo. |
| No avanza de ronda | Faltan ganadores o cupos de clasificación; revisa contadores. |
| Administrador bloqueado temporalmente | Se alcanzaron 10 intentos fallidos en 60 segundos; espera un minuto. |

## Referencias oficiales

- [Streamlit: fragmentos y actualización periódica](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment).
- [Streamlit: Secrets](https://docs.streamlit.io/deploy/concepts/secrets).
- [Streamlit: despliegue en Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
- [Google Sheets: peticiones por lote y atomicidad](https://developers.google.com/workspace/sheets/api/guides/batch).
- [Google Sheets: batchUpdate](https://developers.google.com/workspace/sheets/api/guides/batchupdate).
- [gspread: autenticación con cuentas de servicio](https://docs.gspread.org/en/latest/oauth2.html).
