# Verificación · 29 septiembre 2026

65 pruebas locales aprobadas con Python 3.14, incluida la interfaz real de Streamlit mediante AppTest.

- Cambiar cantidades aplica la distribución sin casilla; una segunda lectura no vuelve a escribir.
- Cambiar grupos con resultados conserva equipos, identidades y clasificación.
- Recorrido libre de 85 equipos: 32 → 16 → 8 → 4 → 2 → campeón.
- Dos equipos que antes eran una pareja pueden clasificar juntos.
- Cada clasificado aparece en la próxima hoja inmediatamente al sincronizar.
- Corregir una clasificación retira solo al equipo afectado de las rondas posteriores.
- Una ronda con exceso de clasificados conserva la entrada manual y no bloquea el cambio de grupos.
- Escrituras incorporan selecciones manuales recientes; se detectan conflictos de revisión.
- Vistas públicas sin controles de escritura; Configuración, Equipos y Administración solo tras autenticación.
- Lectura y escritura de rondas conservan sus datos al serializar y recuperar el torneo.

La sincronización requiere una sesión abierta de Streamlit y consulta cada 10 segundos, con caché de 10 segundos. No funciona como un disparador autónomo de Google Sheets.
