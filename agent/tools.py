"""Herramientas (tools) que el agente puede invocar.

Cada herramienta:
  - tiene un docstring que el LLM lee para decidir cuándo usarla,
  - devuelve (texto para el LLM, dict estructurado para la UI) gracias a
    response_format="content_and_artifact",
  - queda registrada en outputs/registro_acciones.jsonl,
  - nunca lanza excepciones hacia el agente: un fallo inesperado se
    convierte en {"ok": False, "error": "error_interno"}.
"""

from __future__ import annotations

import json
import time
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from agent import audit, services


def _session_id(config: RunnableConfig | None) -> str:
    return ((config or {}).get("configurable") or {}).get("thread_id", "sin_sesion")


def _status(result: dict[str, Any]) -> tuple[str, str]:
    if not result.get("ok"):
        return "error", result.get("error", "desconocido")
    for key in ("resultado", "codigo_rma", "ticket_id"):
        if key in result:
            return "ok", str(result[key])
    return "ok", ""


def _run(name: str, config: RunnableConfig | None, args: dict[str, Any], fn) -> tuple[str, dict[str, Any]]:
    start = time.perf_counter()
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - frontera con el agente: ningún error debe romper la conversación
        result = {
            "ok": False,
            "error": "error_interno",
            "mensaje": "El sistema no respondió correctamente. Ofrece escalar el caso a un agente humano.",
            "detalle_tecnico": f"{type(exc).__name__}: {exc}",
        }
    status, detail = _status(result)
    audit.log_action(_session_id(config), name, args, status, detail, (time.perf_counter() - start) * 1000)
    return json.dumps(result, ensure_ascii=False), result


@tool(response_format="content_and_artifact")
def buscar_politicas_y_faq(consulta: str, config: RunnableConfig) -> tuple[str, dict[str, Any]]:
    """Busca en la base de conocimiento de EcoMarket (política de devoluciones,
    catálogo de productos con precios, preguntas frecuentes sobre envíos,
    pagos y contacto). Úsala para responder preguntas generales que NO
    dependen de un pedido concreto, por ejemplo "¿cuánto cuesta la mochila?"
    o "¿qué métodos de pago aceptan?"."""

    def fn():
        from rag.retriever import search

        chunks, relevant = search(consulta)
        return {
            "ok": True,
            "resultado": "con_informacion" if relevant else "sin_informacion_relevante",
            "hay_informacion_relevante": relevant,
            "instruccion": (
                "Responde solo con base en estos fragmentos."
                if relevant
                else "No hay información relevante: dile al cliente que no lo sabes, no inventes."
            ),
            "fragmentos": [
                {"fuente": c.source, "score_rerank": round(c.rerank_score, 3), "texto": c.content}
                for c in chunks
            ],
        }

    return _run("buscar_politicas_y_faq", config, {"consulta": consulta}, fn)


@tool(response_format="content_and_artifact")
def consultar_pedido(numero_pedido: str, config: RunnableConfig) -> tuple[str, dict[str, Any]]:
    """Consulta el sistema de pedidos: cliente, producto, categoría, estado
    (procesando, en_transito, entregado, cancelado) y fechas. Úsala cuando
    el cliente pregunte por un pedido concreto. El número tiene la forma
    TRK-XXXX."""
    return _run(
        "consultar_pedido",
        config,
        {"numero_pedido": numero_pedido},
        lambda: services.consultar_pedido(numero_pedido),
    )


@tool(response_format="content_and_artifact")
def verificar_elegibilidad_devolucion(
    numero_pedido: str,
    config: RunnableConfig,
    empaque_abierto: bool | None = None,
    producto_con_problema: bool = False,
    motivo: str = "",
) -> tuple[str, dict[str, Any]]:
    """Aplica las reglas de devolución de EcoMarket a un pedido y responde si
    es elegible. Llámala SIEMPRE antes de generar una etiqueta.

    Args:
        numero_pedido: número del pedido (TRK-XXXX).
        empaque_abierto: True/False si el cliente lo dijo; omítelo si no se sabe.
        producto_con_problema: True si el cliente dice que llegó dañado,
            defectuoso, incompleto o vencido.
        motivo: motivo de la devolución en palabras del cliente.

    El campo "resultado" puede ser: elegible, no_elegible,
    requiere_revision_humana o falta_informacion. El campo
    "siguiente_paso" indica qué hacer después."""
    args = {
        "numero_pedido": numero_pedido,
        "empaque_abierto": empaque_abierto,
        "producto_con_problema": producto_con_problema,
        "motivo": motivo,
    }
    return _run(
        "verificar_elegibilidad_devolucion",
        config,
        args,
        lambda: services.verificar_elegibilidad(numero_pedido, empaque_abierto, producto_con_problema, motivo),
    )


@tool(response_format="content_and_artifact")
def generar_etiqueta_devolucion(numero_pedido: str, config: RunnableConfig) -> tuple[str, dict[str, Any]]:
    """Genera la etiqueta de devolución prepagada (con código RMA) de un
    pedido. Solo funciona si verificar_elegibilidad_devolucion ya devolvió
    "elegible" para ese pedido. Si el pedido ya tenía etiqueta, devuelve la
    misma (no crea duplicados)."""
    return _run(
        "generar_etiqueta_devolucion",
        config,
        {"numero_pedido": numero_pedido},
        lambda: services.generar_etiqueta(numero_pedido),
    )


@tool(response_format="content_and_artifact")
def escalar_a_agente_humano(
    motivo: str,
    resumen: str,
    config: RunnableConfig,
    numero_pedido: str | None = None,
    prioridad: Literal["normal", "alta"] = "normal",
) -> tuple[str, dict[str, Any]]:
    """Crea un ticket para que un agente humano de EcoMarket revise el caso.
    Úsala cuando la verificación diga "requiere_revision_humana", cuando el
    cliente lo pida explícitamente, cuando esté molesto o cuando una
    herramienta falle por un error interno. Usa prioridad "alta" si el
    cliente está muy molesto o hay un problema de salud o seguridad."""
    args = {"motivo": motivo, "resumen": resumen, "numero_pedido": numero_pedido, "prioridad": prioridad}
    return _run(
        "escalar_a_agente_humano",
        config,
        args,
        lambda: services.escalar_a_humano(motivo, resumen, numero_pedido, prioridad),
    )


ALL_TOOLS = [
    buscar_politicas_y_faq,
    consultar_pedido,
    verificar_elegibilidad_devolucion,
    generar_etiqueta_devolucion,
    escalar_a_agente_humano,
]
