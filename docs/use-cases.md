# Canonical use cases

Used for agent evaluation tests, model comparison and the demo video.

| # | Input | Expected behavior | Covers |
|---|---|---|---|
| 1 | "Necesito unos auriculares cómodos para trabajar y hacer videollamadas. No quiero gastar más de USD 200." | Semantic search + price filter via tool; recommends 2–3 with reasons and verified prices | RF-02, RF-04, RF-07 |
| 2 | "Quiero un monitor" | Asks for usage and budget before recommending | RF-05 |
| 3 | "Compará el primero con el segundo" | `compare_products` using real specs | RF-06 |
| 4 | "¿Hay stock del <producto>?" | `get_stock` in the current turn | RF-07 |
| 5 | "¿Cuánto sale una PlayStation 9?" | States it is not in the catalog; invents nothing | RF-17, RF-18 |
| 6 | Add 50 units of a product with 7 available | Clear error, cart unchanged | RF-10 |
| 7 | Complete purchase | Order ID, stock decremented, visible in history | RF-13..16 |
| 8 | Case 1 by voice | Transcribed and processed as text | RF-08 |
| 9 | Ollama stopped | Friendly "service unavailable", app keeps working | RNF-04 |
| 10 | "Comprámelo" from chat | Shows confirmation modal; nothing is purchased until confirmed | RF-12 |
