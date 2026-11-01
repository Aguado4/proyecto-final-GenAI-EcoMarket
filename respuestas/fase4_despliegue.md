# Fase 4 — Despliegue de la Aplicación

## Selección de la herramienta: Streamlit

Se escogió **Streamlit** sobre Gradio por:
- **Familiaridad:** ya tenemos experiencia con Streamlit, y la UI del
  Taller 2 ya estaba hecha con él.
- **Propósito:** Streamlit está pensado para apps de datos y dashboards,
  mientras que Gradio está orientado a demos de modelos de ML. Esta app
  necesita más que un chat: el grafo del agente, el panel de monitoreo,
  las tarjetas de etiqueta y los ejemplos en la barra lateral.
- **Flexibilidad:** ofrece lo necesario para el chatbot y es más flexible
  para el layout (pestañas, barra lateral, columnas, métricas, CSS
  propio). Gradio da un chat listo en una línea (`gr.ChatInterface`),
  pero personalizar algo tipo dashboard cuesta más. Con experiencia como
  ingeniero de software, usar una biblioteca más flexible no es un
  problema.

Funcionalidades de Streamlit que usa la app (para apoyar la justificación):
- `st.chat_message` / `st.chat_input` para el chat.
- `st.session_state` para el historial y el `thread_id` de la conversación.
- `st.status` para mostrar en vivo qué está haciendo el agente.
- `st.tabs` para separar chat, grafo y monitoreo.
- `st.cache_resource` para cargar una sola vez el grafo, Chroma y el
  cross-encoder.
- `st.download_button` para descargar la etiqueta y el registro.

## Implementación de la interfaz

`streamlit run app_streamlit.py`

- **Chat:** campo de texto y respuestas del agente. Cuando hay etiqueta,
  se muestra como tarjeta con el código RMA y un botón para descargarla.
  Cuando se escala, se muestra la tarjeta del ticket. Las etiquetas de
  colores indican qué herramientas se usaron y su resultado. La traza
  desplegable muestra los argumentos y respuestas de cada herramienta.
- **Barra lateral:** modelo de Groq, botón de nueva conversación, 8
  ejemplos de un clic y la tabla de pedidos de prueba.
- **Grafo del agente:** el grafo real de LangGraph (nodos y aristas de
  `get_graph()`) con las 5 herramientas expandidas, el camino y las
  herramientas del último turno resaltados, y una leyenda que distingue las
  aristas obligatorias de las condicionales. Debajo, la tabla de herramientas.
- **Monitoreo:** métricas y tabla del registro de acciones.

## Demostración funcional

Guion sugerido para el video (3 a 4 minutos), con los botones de la barra
lateral:

1. **Devolución aprobada** (TRK-2001) → tarjeta de etiqueta. Muestra la traza.
2. **Falta un dato** (TRK-2003) → el agente pregunta. Responde "No, está
   sellado" → genera la etiqueta (memoria de la conversación).
3. **Escala a humano** (TRK-2007) → ticket.
4. **Pregunta general (RAG)** → responde sin herramientas de pedidos.
5. **Prompt injection** → bloqueado por el guardrail.
6. Pestaña **Grafo del agente** (ruta resaltada) y pestaña **Monitoreo**.
