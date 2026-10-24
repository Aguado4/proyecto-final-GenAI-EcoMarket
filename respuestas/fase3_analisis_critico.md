# Fase 3 — Análisis Crítico y Propuestas de Mejora

> Esta fase es de reflexión propia: los bloques **POR COMPLETAR** son para
> tu análisis. Debajo de cada uno hay hechos del sistema (lo que ya hace
> el código) que puedes citar como evidencia.

## Análisis de seguridad y ética

> **POR COMPLETAR:** riesgos nuevos que aparecen cuando la IA no solo
> responde, sino que **actúa** (genera etiquetas, crea tickets), con
> escenarios concretos y cómo mitigarlos.
>
> Preguntas guía:
> - ¿Qué pasa si alguien da el número de pedido de otra persona? (hoy no
>   se verifica la identidad del cliente)
> - ¿Qué pasa si el LLM se equivoca y aprueba algo que no debía? ¿Quién
>   asume el costo?
> - ¿Es justo para el cliente que una IA le niegue una devolución? ¿Debe
>   saber que habla con una IA y poder pedir un humano?
> - Prompt injection: ¿qué cubre el guardrail por reglas y qué no
>   (variantes, otros idiomas, instrucciones escondidas)?
> - Privacidad: ¿qué datos personales ve el LLM y dónde quedan guardados?
> - Sesgos: ¿el tono o el criterio cambia según cómo escribe el cliente?

Mitigaciones que **ya implementa** el código (para citar):
- Las reglas de elegibilidad son código determinista, no criterio del
  LLM. La etiqueta se niega sin una verificación `elegible` previa.
- Las etiquetas son idempotentes: una por pedido, sin duplicados ni
  abuso de reenvíos.
- Guardrail de entrada contra prompt injection, mensajes vacíos y
  mensajes demasiado largos.
- `consultar_pedido` enmascara el email y no expone la dirección.
- Los casos ambiguos o de excepción se escalan a un humano en vez de
  decidirse automáticamente.
- Límite de pasos del grafo para cortar bucles.
- Las herramientas nunca exponen detalles técnicos del error al cliente.

## Monitoreo y observabilidad

> **POR COMPLETAR:** tu propuesta de cómo asegurar que el agente funciona
> bien en producción. Qué medirías, qué alertas pondrías y con qué
> umbrales, y quién revisa qué.

Lo que ya existe (para construir sobre ello):
- `outputs/registro_acciones.jsonl`: cada llamada a herramienta queda
  registrada con sesión, argumentos, estado, detalle y latencia.
- Pestaña **Monitoreo** en la app: total de acciones, etiquetas,
  escalamientos, errores, latencia media y gráfico por herramienta.
- Traza por respuesta en la UI: ruta en el grafo y argumentos y
  resultados de cada herramienta.
- `python -m agent.evaluate` como prueba de regresión del comportamiento
  (por ejemplo, correrla antes de cambiar el prompt o el modelo).

## Propuestas de mejora

> **POR COMPLETAR:** otras funcionalidades con agentes. El enunciado
> sugiere crear una orden de reemplazo o actualizar el CRM. Piensa qué
> herramientas nuevas implicaría cada una y qué riesgos agregaría.
