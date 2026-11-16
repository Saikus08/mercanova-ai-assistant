# Flujo de una herramienta del asistente

Estos diagramas muestran lo que está implementado en el dispatcher y las herramientas de lectura (decisión 0005). El ciclo del agente que llama al dispatcher es otra tarea: hoy se invoca directamente.

## 1. Qué comprueba el dispatcher antes de ejecutar

```mermaid
flowchart TD
    A[El modelo pide una herramienta<br/>nombre + argumentos] --> B{¿Los argumentos<br/>son un objeto?}
    B -- no --> E1[error + hint:<br/>mandar un objeto JSON]
    B -- sí --> C{¿Herramienta<br/>prohibida?}
    C -- sí --> E2[error + hint:<br/>solo el usuario confirma<br/>desde la interfaz]
    C -- no --> D{¿Existe?}
    D -- no --> E3[error + hint:<br/>lista de herramientas<br/>y sugerencia]
    D -- sí --> F{¿Trae session_id?}
    F -- sí --> E4[error + hint:<br/>lo pone el sistema]
    F -- no --> G{¿Cumple<br/>el esquema?}
    G -- no --> E5[error + hint:<br/>campo, problema<br/>y esquema esperado]
    G -- sí --> H[Ejecuta la herramienta<br/>con el session_id del sistema]
    H --> I{¿Falló?}
    I -- error conocido --> E6[error + hint<br/>producto inexistente,<br/>búsqueda no disponible, etc.]
    I -- error inesperado --> E7[error genérico<br/>sin detalles técnicos]
    I -- no --> OK[Resultado estructurado]
```

Todos los errores tienen la misma forma, `{"error": ..., "hint": ...}`, y vuelven al modelo para que corrija el pedido. El dispatcher nunca lanza una excepción hacia el usuario.

## 2. Una búsqueda de punta a punta

El caso de uso 1: "auriculares para videollamadas, máximo USD 200".

```mermaid
sequenceDiagram
    participant M as Modelo (simulado)
    participant D as Dispatcher
    participant T as Herramienta search_products
    participant S as Caso de uso de búsqueda
    participant O as Ollama
    participant DB as PostgreSQL

    M->>D: search_products(query, category, max_price)
    D->>D: permisos, nombre, session_id, esquema
    D->>T: argumentos válidos + contexto de sesión
    T->>S: consulta, filtros, mínimo 0.62
    S->>O: vector de la consulta
    O-->>S: vector
    S->>DB: los 5 más cercanos con filtros
    DB-->>S: ids y puntajes
    S-->>T: los que superan el mínimo
    alt ninguno supera el mínimo
        T-->>D: lista vacía + nota "decile al usuario que no lo tenemos"
    else hay resultados
        T->>DB: precio y stock de esos productos, en esta llamada
        DB-->>T: valores actuales
        T-->>D: productos con precio, stock y similitud
    end
    D-->>M: resultado o error con hint
```

El precio y el stock no salen del índice: se leen de sus tablas cada vez que se ejecuta la herramienta.

## 3. Clases

```mermaid
classDiagram
    direction LR

    class ToolDispatcher {
        dispatch(name, arguments, context) ToolResult
    }
    class ToolRegistry {
        specs() ToolSpec[]
        get(name) Tool
        names() str[]
    }
    class Tool {
        name
        description
        args_model
        handler
    }
    class ToolContext {
        session_id
    }
    class ToolResult {
        tool
        ok
        payload
        duration_ms
    }
    class Permission {
        <<enumeration>>
        FREE
        CONFIRMATION
        FORBIDDEN
    }
    class PERMISSIONS {
        <<tabla>>
        nombre de herramienta a permiso
    }

    ToolDispatcher --> ToolRegistry : consulta
    ToolDispatcher ..> PERMISSIONS : verifica
    ToolDispatcher ..> ToolContext : se lo pasa a la herramienta
    ToolDispatcher ..> ToolResult : devuelve
    ToolRegistry o-- Tool : registra
    ToolRegistry ..> PERMISSIONS : rechaza prohibidas y desconocidas
    PERMISSIONS --> Permission
```

`ToolContext` lo arma el sistema, no el modelo. El registro se niega a aceptar `confirm_order` y `cancel_order`: por eso no existe ningún camino por el que el modelo pueda confirmar una compra.
