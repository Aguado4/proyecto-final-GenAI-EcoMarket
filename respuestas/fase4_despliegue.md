# Fase 4 — Despliegue de la Aplicación

## Selección de la herramienta: Streamlit

> **POR COMPLETAR (tu justificación):** tu razón principal fue que ya
> tienes experiencia con Streamlit (y el Taller 2 ya tenía su UI en
> Streamlit). Puedes compararlo con Gradio en facilidad de uso y
> funcionalidad.

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
- **Grafo del agente:** el grafo real de LangGraph (`draw_mermaid()`),
  con los nodos del último turno resaltados, más la tabla de herramientas.
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
