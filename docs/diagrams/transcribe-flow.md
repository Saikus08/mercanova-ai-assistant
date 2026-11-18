# Flujo de voz a texto

Este diagrama muestra lo que está implementado en `POST /api/transcribe`, la entrada por voz que pide la letra (RF-08). El endpoint solo convierte el audio en texto. Después, el frontend manda ese texto a `/api/chat/stream` con `input_mode: "voice"`, y la consulta sigue el mismo camino que una escrita (ver `chat-flow.md`). El botón de voz del frontend todavía no existe.

La transcripción corre en el mismo contenedor del backend, con faster-whisper en CPU (decisión 0001). El modelo (`STT_MODEL`, por defecto `small`) se descarga la primera vez que se usa y queda en el volumen `whisper_models`. Se carga una sola vez por proceso.

```mermaid
sequenceDiagram
    participant U as Navegador
    participant A as Endpoint /api/transcribe
    participant C as Caso de uso transcribe_audio
    participant W as Adaptador faster-whisper
    participant M as Modelo Whisper (CPU)

    U->>A: POST multipart, campo audio (webm, ogg o wav)
    A->>A: lee hasta 10 MB + 1 byte
    A->>C: bytes y tipo de contenido
    alt formato no admitido o más de 10 MB
        C-->>A: InvalidAudio
        A-->>U: 400 VALIDATION_ERROR (field audio)
    else audio vacío
        C-->>A: AudioUnreadable
        A-->>U: 422 AUDIO_UNREADABLE
    end
    C->>W: transcribe(bytes, máximo 60 s)
    W->>W: decodifica con PyAV a 16 kHz mono
    alt no se puede decodificar o no tiene muestras
        W-->>A: AudioUnreadable
        A-->>U: 422 AUDIO_UNREADABLE
    else dura más de 60 s
        W-->>A: InvalidAudio, sin correr el modelo
        A-->>U: 400 VALIDATION_ERROR
    end
    W->>M: carga el modelo si es la primera vez
    W->>M: transcribe en español, con filtro de silencios
    alt el modelo no carga o falla
        W-->>A: SpeechToTextUnavailable
        A-->>U: 503 STT_UNAVAILABLE
    end
    M-->>W: segmentos de texto e idioma
    W-->>C: Transcript (texto, idioma, duración)
    alt el texto queda vacío (no había voz)
        C-->>A: AudioUnreadable
        A-->>U: 422 AUDIO_UNREADABLE
    else
        C-->>A: Transcript con el texto recortado
        A-->>U: 200 { text, language, duration_s }
    end
```

Los mensajes de error que ve el usuario están en español y nunca incluyen el detalle técnico de la falla. Ese detalle queda solo en el log del backend.
