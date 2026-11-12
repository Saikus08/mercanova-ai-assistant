# Casos de uso de referencia

Estos 10 casos se usan para tres cosas: los tests del asistente, la comparación de modelos y el video de demostración. Cada uno indica qué tiene que hacer la aplicación y qué requerimiento de la letra demuestra.

| # | El usuario hace o dice | La aplicación debe | Requerimiento que demuestra |
|---|---|---|---|
| 1 | "Necesito unos auriculares cómodos para trabajar y hacer videollamadas. No quiero gastar más de USD 200." | Buscar por significado, filtrar por precio y recomendar 2 o 3 productos explicando por qué, con el precio leído de la base | Búsqueda en lenguaje natural (RF-02), recomendaciones explicadas (RF-04), información actual (RF-07) |
| 2 | "Quiero un monitor" | Preguntar para qué lo va a usar y cuánto quiere gastar antes de recomendar | Pedir aclaraciones (RF-05) |
| 3 | "Compará el primero con el segundo" | Mostrar una tabla con las especificaciones reales de ambos | Comparación (RF-06) |
| 4 | "¿Hay stock del <producto>?" | Consultar el stock en ese momento, no de memoria | Información actual (RF-07) |
| 5 | "¿Cuánto sale una PlayStation 9?" (no existe) | Decir que no está en el catálogo, sin inventar precio ni datos | Casos límite (RF-17) y no inventar información (RF-18) |
| 6 | Agregar 50 unidades de un producto que tiene 7 disponibles | Mostrar un error claro y no modificar el carrito | Validación de disponibilidad (RF-10) |
| 7 | Completar una compra | Generar un número de orden, descontar el stock y mostrar la orden en el historial | Compra, orden, actualización de stock e historial (RF-13 a RF-16) |
| 8 | El caso 1, dicho por voz | Transcribir el audio y responder igual que si fuera texto | Entrada por voz (RF-08) |
| 9 | Ollama apagado | Mostrar "el asistente no está disponible" y que el resto de la tienda siga funcionando | Robustez (RNF-04) |
| 10 | "Comprámelo" en el chat | Abrir la ventana de confirmación. Nada se compra hasta que el usuario hace clic en "Confirmar compra" | Confirmación explícita (RF-12) |
