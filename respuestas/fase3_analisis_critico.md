# Fase 3 — Análisis Crítico y Propuestas de Mejora

## Análisis de seguridad y ética

El principal riesgo nuevo de darle a la IA la capacidad de tomar acciones
es que **puede ejecutar acciones que el usuario no quería y que le
resulten perjudiciales**. Por eso hay que **limitar mucho el uso de
herramientas**: darle al agente solo las acciones estrictamente
necesarias y con reglas claras sobre cuándo puede ejecutarlas.

En este proyecto, ese límite se aplica así:
- Las reglas de elegibilidad son código determinista, no criterio del
  LLM. La etiqueta se niega sin una verificación `elegible` previa.
- Las etiquetas son idempotentes: una por pedido, sin duplicados.
- Guardrail de entrada contra prompt injection, mensajes vacíos y
  mensajes demasiado largos.
- `consultar_pedido` enmascara el email y no expone la dirección.
- Los casos ambiguos o de excepción se escalan a un humano en vez de
  decidirse automáticamente.
- Límite de pasos del grafo para cortar bucles.
- Las herramientas nunca exponen detalles técnicos del error al cliente.

## Monitoreo y observabilidad

Se puede monitorear con distintas plataformas de observabilidad,
preferiblemente usando **OpenTelemetry** como estándar, registrando por
cada interacción:
- La información que envía el usuario y la respuesta del agente.
- Qué herramientas usa el agente.
- El costo de cada interacción.
- Si usa el RAG, qué documentos recupera.

Además, se pueden agregar **guardrails** que detecten de forma
determinista palabras peligrosas, insultos o señales de que el usuario
está frustrado, para manejar mejor la conversación (por ejemplo,
escalando a un humano a tiempo).

Base que ya existe en el proyecto:
- `outputs/registro_acciones.jsonl`: cada llamada a herramienta queda
  registrada con sesión, argumentos, estado, detalle y latencia.
- Pestaña **Monitoreo** en la app: total de acciones, etiquetas,
  escalamientos, errores, latencia media y gráfico por herramienta.
- Traza por respuesta en la UI: ruta en el grafo y argumentos y
  resultados de cada herramienta.
- `python -m agent.evaluate` como prueba de regresión del comportamiento.

## Propuestas de mejora

- **Dictado por voz:** para que la aplicación sea más accesible para
  personas con dificultades motrices.
- **Botón para escalar a un humano:** que el usuario pueda pedirlo
  directamente, sin depender de que el agente lo decida.
- **Visualización de pedidos:** herramientas que muestren los pedidos
  del cliente en gráficos o tablas.
- **Integración con un CRM:** actualizar la información del cliente y
  consultar sus pedidos previos.
- **Agendamiento de reuniones:** conectar con una aplicación como
  Calendly para que, si el usuario quiere reunirse con un agente de
  ventas, pueda agendar la reunión desde el mismo chat sin cambiar de
  aplicación.
