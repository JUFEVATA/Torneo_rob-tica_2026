# Verificación · 29 de septiembre de 2026

## Entrega por rondas

- 49 pruebas locales con Python 3.14: dominio, persistencia, Google Sheets simulado y Streamlit AppTest.
- Importación del boletín proporcionado: 85 equipos, grupos 22 / 21 / 21 / 21, 32 cupos, nombres originales.
- Recorrido automatizado completo: grupos → dieciseisavos → octavos → cuartos → semifinal → final → campeón. Comprobación de participantes restantes e historial de todas las fases.
- Rechazo de importaciones incompletas, duplicados y resultados incompatibles; correcciones confirmadas y detección de revisiones obsoletas.
- Menú público sin Configuración, Equipos ni Administración; importación y desplegable del administrador probados con AppTest.
- Inspección visual en navegador local: nueva navegación y paleta EPM. Los colores proceden del brief del usuario en la tarea «Crear app local de sorteos STEM».

## Google Sheets real

- Cargados los 85 equipos en el libro indicado por el usuario, todos Pendiente.
- Verificados por API los 85 desplegables y las seis hojas visibles: Grupos, 16 avos, 8vos, 4tos, Semifinal y Final.
- Prueba real: una clasificación temporal introducida en la celda del desplegable fue importada al estado del torneo; después se restauró Pendiente y se verificó la restauración completa.
- Las lecturas repetidas conservan la misma revisión y no regeneran el torneo.
- Copias de las seis tablas previas conservadas como hojas ocultas «_Antes rondas …»; respaldos anteriores preservados.
- La comprobación de Sheets se realizó con su API autenticada; no se verificó su apariencia en una sesión nativa de Google Sheets iniciada en el navegador.

La sincronización necesita una sesión de Streamlit abierta. Las pruebas locales y de API no equivalen a verificar la actualización de un despliegue concreto de Streamlit Community Cloud.
