# Verificación · 30 septiembre 2026

80 pruebas locales aprobadas con Python 3.14, incluida la interfaz real de Streamlit mediante AppTest.

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
