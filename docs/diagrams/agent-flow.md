# Flujo de un turno del asistente

Estos diagramas muestran lo que está implementado en el ciclo del agente (decisión 0009). El endpoint de chat invoca este ciclo, guarda el estado entre mensajes y arma los bloques de la respuesta (ver `chat-flow.md`).

## 1. Un turno, de punta a punta

```mermaid
sequenceDiagram
    participant U as Usuario
    participant L as Ciclo del agente
    participant M as Modelo (Ollama)
    participant D as Dispatcher y herramientas
    participant DB as PostgreSQL

    U->>L: mensaje
    L->>L: arma el contexto: prompt + estado + últimos 8 mensajes
    rect rgb(240, 245, 255)
    Note over L,D: Fase de herramientas (hasta AGENT_MAX_STEPS)
    loop mientras el modelo pida herramientas
        L->>M: mensajes + herramientas
        M-->>L: texto o pedido de herramienta
        L->>L: controles previos (ver diagrama 2)
        L->>D: dispatch(herramienta, argumentos, sesión del sistema)
        D->>DB: lee precio y stock del momento
        DB-->>D: datos actuales
        D-->>L: resultado o error con pista
        L->>L: actualiza el estado (productos mostrados, herramientas usadas)
    end
    end
    rect rgb(245, 255, 245)
    Note over L,M: Fase final (una respuesta estructurada)
    L->>M: transcripción + instrucción + esquema JSON, sin herramientas
    M-->>L: JSON: texto, recomendaciones, aclaración, no encontrado
    L->>L: controles de la respuesta (ver diagrama 3)
    end
    L-->>U: texto + tarjetas armadas con datos de las herramientas
```

Si el modelo no responde, o se alcanza el máximo de pasos, el ciclo devuelve un mensaje fijo en español y marca el resultado como degradado. El ciclo no deja una excepción en manos del usuario.

## 2. Controles antes de ejecutar una herramienta

```mermaid
flowchart TD
    A[El modelo pide una herramienta] --> B{¿Pide un filtro de precio<br/>que el cliente no dijo?}
    B -- sí --> X1[No se ejecuta.<br/>Error: no inventes filtros]
    B -- no --> C{¿Es una búsqueda con 3 palabras o<br/>menos en total, sin números<br/>y sin filtros?}
    C -- sí --> X2[No se ejecuta.<br/>Error: hacé una pregunta primero]
    C -- no --> D[Dispatcher: herramienta, permisos,<br/>session_id y esquema<br/>el id de producto no puede ser un nombre]
    D -- inválida --> X3[Error con pista]
    D -- válida --> E[Se ejecuta y se actualiza el estado]
    X1 --> R{¿Segunda llamada inválida<br/>seguida?}
    X2 --> R
    X3 --> R
    R -- no --> S[El modelo puede corregir una vez]
    R -- sí --> T[Se corta el turno:<br/>respuesta degradada]
```

## 3. Controles de la respuesta final

```mermaid
flowchart TD
    A[JSON del modelo] --> B{¿Cumple el esquema?}
    B -- no --> B1[Un reintento]
    B1 -- sigue mal --> Z1[Respuesta degradada]
    B -- sí --> C{¿Un monto del texto no vino<br/>de una herramienta ni del cliente,<br/>o nombra una herramienta?}
    C -- sí --> C1[Un reintento]
    C1 -- sigue mal --> Z2[Respuesta degradada]
    C -- no --> D{¿Se bloqueó una búsqueda vaga<br/>y no hay aclaración?}
    D -- sí --> D1[Un reintento, y si no,<br/>pregunta fija sin recomendaciones]
    D -- no --> E{¿Hay productos encontrados<br/>pero ninguna recomendación?}
    E -- sí --> E1[Un reintento y, si no,<br/>los 3 primeros resultados<br/>marcados fallback_used]
    E -- no --> F[Se arma el resultado:<br/>tarjetas con datos de la herramienta,<br/>ids desconocidos descartados]
    D1 --> F
    E1 --> F
```

## 4. Clases

```mermaid
classDiagram
    direction LR

    namespace Dominio {
        class AgentState {
            goal
            shown_products
            tools_used
            step
            describe()
        }
        class ChatMessage {
            role
            content
            tool_calls
        }
        class StopReason {
            <<enumeration>>
            ANSWER
            MAX_STEPS
            LLM_UNAVAILABLE
            INVALID_TOOL_CALLS
            INVALID_ANSWER
            UNGROUNDED_ANSWER
        }
    }

    namespace Aplicacion {
        class AgentLoop {
            run_turn()
        }
        class ChatModel {
            <<puerto>>
            chat(messages, tools, schema)
        }
        class grounding {
            <<funciones>>
            too_vague_search
            ungrounded_price_filters
            ungrounded_amounts
            leaked_tool_names
        }
        class prompts {
            SYSTEM_PROMPT
            build_context
            FINAL_INSTRUCTION
        }
        class FinalAnswer {
            reply
            recommendations
            clarification
            not_found
        }
        class TurnResult {
            reply
            recommendations
            tools_used
            stop_reason
            degraded
            fallback_used
        }
    }

    namespace Adaptadores {
        class OllamaChat {
            POST api/chat
        }
        class ToolDispatcher
    }

    AgentLoop ..> ChatModel : usa
    AgentLoop ..> ToolDispatcher : ejecuta herramientas
    AgentLoop ..> AgentState : actualiza
    AgentLoop ..> grounding : controla
    AgentLoop ..> prompts : arma el contexto
    AgentLoop ..> FinalAnswer : valida
    AgentLoop ..> TurnResult : devuelve
    ChatModel <|.. OllamaChat : implementa
    TurnResult --> StopReason
    AgentLoop ..> ChatMessage : recibe el historial
```

`AgentState` guarda lo que el asistente necesita recordar (productos mostrados en orden, herramientas usadas, paso) y no la conversación. El historial de mensajes es otra cosa: llega como parámetro y se recorta a los últimos mensajes.
