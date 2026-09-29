# Verificación de la entrega

Fecha: 28 de septiembre de 2026.

## Resultado ejecutado

```text
python -m unittest discover -s tests -v
Ran 41 tests
OK

python -m compileall -q app.py core services components utils tests
Sin errores

python -m pip check
No broken requirements found.
```

Entorno local: Python 3.14.6; Streamlit 1.64.0; pandas 3.0.6; gspread 6.2.1; google-auth 2.59.0. La matriz de CI de Python 3.12/3.13/3.14 está configurada, pero no se ha ejecutado en GitHub desde esta entrega.

## Cobertura comprobada

- Los cinco casos obligatorios: 10/3, 17/4, 23/5, 32/6 y 32/8.
- Conservación de suma, grupos no vacíos, orden de sobrantes y diferencia máxima de uno para todas las combinaciones válidas de 1 a 199 equipos.
- Distribución circular exacta, sorteo guardado, grupos AA y AB.
- Torneos completos con 2, 4, 8, 16, 32 y 64 clasificados; 32 participantes producen 31 partidos y un campeón.
- Bloqueo de fases duplicadas, cupos incompletos, partidos contra sí mismo y ganadores ajenos al cruce.
- Correcciones con confirmación, anulación de resultados descendientes y conservación de ramas independientes.
- Reinicios confirmados, aislamiento entre competencias y nombres de equipos editables sin romper referencias.
- Serialización de las seis pestañas; recuperación del campeón; rechazo de datos manuales inválidos.
- Persistencia en archivo al abrir otro repositorio/sesión; rechazo de escrituras antiguas y dos escrituras simultáneas dentro de un proceso.
- Adaptador de Google Sheets probado con una API simulada: creación de pestañas, un solo commit por lote, edición manual detectada, fallo de escritura y eliminación de filas antiguas.
- Importación CSV y neutralización de nombres que aparentan fórmulas.
- AppTest: nueve pantallas públicas y de administrador, contraseña incorrecta, creación desde cero, grupos, torneo completo desde widgets, edición persistente entre sesiones y reinicio con doble confirmación.

## Revisión de navegador

Se inició Streamlit localmente y se revisó la vista pública con los datos de demostración. Se verificaron tarjetas y métricas adaptables en tamaños de escritorio (1440 px) y móvil (390 px). Las métricas se ajustaron a una cuadrícula que evita truncarlas en pantallas estrechas.

Se recargó el navegador y se detuvo/reinició el proceso Streamlit. Los 32 equipos, distribución 6/6/5/5/5/5 y 12 clasificados de demostración se conservaron en el archivo local. Las pruebas AppTest verifican además una sesión nueva sobre el mismo repositorio persistente.

## Pendiente en tu infraestructura

No se proporcionaron credenciales reales, ID de Google Sheet ni repositorio remoto. Por tanto, **no se ha afirmado ni verificado una conexión real a Google Sheets, un push a GitHub o un despliegue en Streamlit Community Cloud**.

Antes del evento, completa los pasos de Google Cloud y Secrets del README y ejecuta su lista de aceptación en la hoja real: F5, cierre del navegador, reinicio de Streamlit, segunda sesión y actualización desde Sheets.

La aplicación implementa bloqueos dentro del proceso, detección de estado desactualizado y escrituras atómicas por lote. Sheets no ofrece compare-and-swap para excluir una edición externa en la ventana entre lectura y escritura: usa un único despliegue escritor y coordina las ediciones manuales.
