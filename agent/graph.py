"""Grafo del agente con LangGraph.

    START -> validar_entrada --(bloqueado)--> respuesta_bloqueada -> END
                     |
                     +--(ok)--> agente <--> herramientas
                                   |
                                   +--(sin llamadas a herramientas)--> END

- validar_entrada: guardrail por reglas (mensaje vacío, demasiado largo o
  intento de prompt injection). No usa el LLM.
- agente: el LLM (Groq) con las herramientas enlazadas decide si responde
  directamente o pide ejecutar una o varias herramientas.
- herramientas: ejecuta las herramientas pedidas y devuelve el resultado
  al agente, que vuelve a decidir (bucle ReAct).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent import config
from agent.prompt_loader import load_prompt
from agent.tools import ALL_TOOLS

MAX_INPUT_CHARS = 1500

INJECTION_PATTERNS = [
    r"ignora\w*\s+(todas\s+)?(las\s+|tus\s+)?(instrucciones|reglas)",
    r"ignore\s+(all\s+|your\s+|previous\s+)*instructions",
    r"(revela|mu[eé]stra|dime)\w*\s+(tu|tus|el|las)\s+(prompt|instrucciones)",
    r"system\s*prompt",
    r"modo\s+(desarrollador|developer|dios)",
    r"jailbreak",
]

BLOCKED_MESSAGE = (
    "Lo siento, no puedo procesar ese mensaje. Puedo ayudarte con devoluciones, "
    "el estado de tus pedidos o dudas sobre productos, envíos y pagos de EcoMarket."
)
RECURSION_MESSAGE = (
    "No logré completar tu solicitud en este momento. Para no dejarte sin "
    "respuesta, te recomiendo pedirme que escale tu caso a un agente humano."
)


class AgentState(MessagesState):
    bloqueado: bool
    motivo_bloqueo: str


def _check_input(text: str) -> str | None:
    if not text.strip():
        return "mensaje_vacio"
    if len(text) > MAX_INPUT_CHARS:
        return "mensaje_demasiado_largo"
    lowered = text.lower()
    if any(re.search(p, lowered) for p in INJECTION_PATTERNS):
        return "posible_prompt_injection"
    return None


def validar_entrada(state: AgentState) -> dict[str, Any]:
    last = state["messages"][-1]
    motivo = _check_input(last.content if isinstance(last.content, str) else str(last.content))
    return {"bloqueado": motivo is not None, "motivo_bloqueo": motivo or ""}


def ruta_entrada(state: AgentState) -> Literal["agente", "respuesta_bloqueada"]:
    return "respuesta_bloqueada" if state.get("bloqueado") else "agente"


def respuesta_bloqueada(state: AgentState) -> dict[str, Any]:
    return {"messages": [AIMessage(content=BLOCKED_MESSAGE)]}


def build_graph(model: str = config.DEFAULT_MODEL, prompt_version: int | None = None, checkpointer=None):
    llm = ChatGroq(model=model, temperature=0, api_key=config.require_api_key(), max_retries=2)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    system_prompt = load_prompt(prompt_version)["prompts"]["system_prompt"].replace(
        "{fecha_hoy}", config.SIMULATED_TODAY.isoformat()
    )

    def agente(state: AgentState) -> dict[str, Any]:
        response = llm_with_tools.invoke([SystemMessage(content=system_prompt), *state["messages"]])
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("validar_entrada", validar_entrada)
    builder.add_node("respuesta_bloqueada", respuesta_bloqueada)
    builder.add_node("agente", agente)
    builder.add_node("herramientas", ToolNode(ALL_TOOLS))

    builder.add_edge(START, "validar_entrada")
    builder.add_conditional_edges("validar_entrada", ruta_entrada)
    builder.add_edge("respuesta_bloqueada", END)
    builder.add_conditional_edges("agente", tools_condition, {"tools": "herramientas", END: END})
    builder.add_edge("herramientas", "agente")

    return builder.compile(checkpointer=checkpointer or InMemorySaver())


@dataclass
class ToolCallTrace:
    name: str
    args: dict[str, Any]
    result: dict[str, Any] | None = None


@dataclass
class TurnResult:
    answer: str
    path: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    blocked_reason: str = ""
    error: str = ""


def new_thread_id() -> str:
    return uuid.uuid4().hex[:12]


def run_turn(graph, user_text: str, thread_id: str, on_step=None) -> TurnResult:
    """Ejecuta un turno de conversación y devuelve la respuesta con su traza.

    on_step(nodo, update) se llama en vivo por cada nodo ejecutado (la UI lo
    usa para mostrar el progreso)."""
    run_config = {"configurable": {"thread_id": thread_id}, "recursion_limit": config.MAX_GRAPH_STEPS}
    result = TurnResult(answer="")
    pending: dict[str, ToolCallTrace] = {}

    try:
        for chunk in graph.stream(
            {"messages": [HumanMessage(content=user_text)]}, run_config, stream_mode="updates"
        ):
            for node, update in chunk.items():
                result.path.append(node)
                update = update or {}
                if update.get("bloqueado"):
                    result.blocked_reason = update.get("motivo_bloqueo", "")
                for msg in update.get("messages", []):
                    if isinstance(msg, AIMessage):
                        for call in msg.tool_calls:
                            trace = ToolCallTrace(name=call["name"], args=call["args"])
                            pending[call["id"]] = trace
                            result.tool_calls.append(trace)
                        if msg.content and not msg.tool_calls:
                            result.answer = msg.content
                    elif isinstance(msg, ToolMessage) and msg.tool_call_id in pending:
                        pending[msg.tool_call_id].result = msg.artifact if isinstance(msg.artifact, dict) else {
                            "ok": msg.status != "error",
                            "mensaje": str(msg.content),
                        }
                if on_step:
                    on_step(node, update)
    except GraphRecursionError:
        result.error = "limite_de_pasos"
        result.answer = RECURSION_MESSAGE
    except Exception as exc:  # noqa: BLE001 - errores del proveedor del LLM (red, cuota, etc.)
        result.error = f"{type(exc).__name__}: {exc}"
        result.answer = (
            "Tuve un problema técnico para procesar tu solicitud. Por favor intenta "
            "de nuevo en unos segundos; si persiste, un agente humano puede ayudarte."
        )

    if not result.answer and not result.error:
        result.answer = RECURSION_MESSAGE
    return result


def graph_mermaid(graph) -> str:
    return graph.get_graph().draw_mermaid()
