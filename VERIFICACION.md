# Verificación · 2 octubre 2026

112 pruebas locales aprobadas con Python 3.14, incluida la interfaz real de Streamlit mediante AppTest.

- Cambiar cantidades aplica la distribución sin casilla; una segunda lectura no vuelve a escribir.
- Cambiar grupos con resultados conserva equipos, identidades y clasificación.
- Recorrido libre de 85 equipos: 32 → 16 → 8 → 4 → 2 → campeón.
- Dos equipos que antes eran una pareja pueden clasificar juntos.
- Cada clasificado aparece en la próxima hoja inmediatamente al sincronizar.
- Corregir una clasificación retira solo al equipo afectado de las rondas posteriores.
- Una ronda con exceso de clasificados conserva la entrada manual y no bloquea el cambio de grupos.
- Escrituras incorporan selecciones manuales recientes; se detectan conflictos de revisión.
- Acceso discreto al pulsar Equipo STEM 2026; formulario oculto al abrir la página y tras cerrar sesión.
- Inicio presenta cada ronda en un único panel con columnas adaptables y nombres completos de las fases; ninguna vista pública ofrece tablas con descarga CSV.
- Menú lateral sin la leyenda TORNEO; competencia más destacada, radio seleccionado con punto interior y botón Entrar azul con texto blanco.
- Hoja Podio visible, con tres filas por competencia, desplegables de equipos y sincronización bidireccional. Una selección inválida se conserva para corregirla y no bloquea las otras hojas.
- Menú público limitado a Inicio, Fases y Podio, sin selector de competencia.
- Publicación compartida con etapa automática o manual; el cambio se refleja al abrir otra sesión.
- Podio manual de tres posiciones con validación de equipos únicos y persistencia después de sincronizar Sheets.
- Eliminar y restaurar la última competencia conserva equipos, rondas, podio y configuración.
- Papelera dividida en partes para respetar el tamaño máximo de las celdas de Sheets.
- Cerrar sesión desde una página administrativa vuelve a la navegación pública.
- Árbol visual con nombres y estados, conexión de etapas, vista completa y ampliación; nombres escapados para evitar interpretar HTML.
- Revisión visual local de Inicio, árbol completo y ampliado, y Podio.
- Caché de lectura almacena datos básicos para evitar errores de serialización durante actualizaciones del código.
- Lectura y escritura de rondas conservan sus datos al serializar y recuperar el torneo.

La sincronización requiere una sesión abierta de Streamlit y consulta cada 10 segundos, con caché de 10 segundos. No funciona como un disparador autónomo de Google Sheets.

Los datos reales se conservan durante esta actualización. Las pruebas de borrado/restauración y podio usan repositorios temporales; no se asignan ganadores ni se elimina una competencia real durante la verificación.

Verificaciones de recuperación y seguidor de línea:

- Recorrido por tiempos de 32 → 16 → 8 → 4 → podio; precisión de milisegundos, mejor intento y límite de 90 segundos.
- Tres fallos nuevos por fase, descalificación por tres fallos, ausencia y decisiones del juez.
- Cierre con los tres intentos registrados o decisión del juez; empates que afectan cupos/podio exigen desempate explícito.
- Corrección en fase 1 tras cerrar la final reabre la fase afectada, preserva los tiempos de los participantes que permanecen y limpia el campeón antiguo.
- Entrada y cierre desde las hojas de tiempos actualizan la siguiente fase; las proyecciones antiguas no deshacen una corrección anterior.
- Corrección de grupos y ganadores en torneos por parejas después de la final conserva las ramas no afectadas.
- Recuperación forzada con entrada visible inválida, configuración ilegible o ganador inexistente; reinicio de resultados conserva equipos; reinicio completo permite volver a configurar.
- Borrado de la competencia dañada conserva otras competencias y guarda las entradas originales; revisión obsoleta impide sobrescribir una edición concurrente.
- Acceso de administrador y recuperación desde el error inicial comprobados con AppTest.
- Interfaz de tiempos captura minutos, segundos y milisegundos y todas sus páginas públicas carecen de CSV.
- Reducir el número de equipos de seguidor de línea por debajo de 16 adapta la configuración interna y conserva los nombres restantes en Reserva; no exige modificar los cupos del reglamento.

Verificación de columnas de tiempo separadas:

- Cada intento y mejor tiempo tienen MM, SS y MS numéricos. Los ceros y milisegundos se conservan exactamente.
- Encabezados agrupados y colores distintos por intento; N.º, Grupo y Equipo identifican cada fila.
- Las tres casillas vacías representan un intento pendiente; un tiempo requiere las tres casillas completas. Rangos inválidos, fracciones y fórmulas se rechazan sin borrar la entrada para corregirla.
- La migración incorpora hojas anteriores sin cambiar los tiempos, intentos no completados o fases cerradas.
- Los cambios al mejor tiempo calculado no modifican los intentos ni la clasificación.
- Reinicio forzado con la nueva estructura conserva otras competencias.
- La vista pública del mejor tiempo y el historial administrativo presentan minutos, segundos y milisegundos separados.
