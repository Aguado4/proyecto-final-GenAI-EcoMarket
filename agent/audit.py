"""Registro de acciones del agente (observabilidad).

Cada llamada a una herramienta queda como una línea JSON en
outputs/registro_acciones.jsonl: quién (sesión), qué (herramienta y
argumentos), con qué resultado y cuánto tardó. La UI lo lee para el panel
de monitoreo.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from agent import config


def log_action(
    session_id: str,
    tool: str,
    args: dict[str, Any],
    status: str,
    detail: str,
    duration_ms: float,
) -> None:
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_id": session_id,
        "tool": tool,
        "args": args,
        "status": status,
        "detail": detail,
        "duration_ms": round(duration_ms, 1),
    }
    with config.AUDIT_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_actions(limit: int | None = None) -> list[dict[str, Any]]:
    if not config.AUDIT_LOG_FILE.exists():
        return []
    lines = config.AUDIT_LOG_FILE.read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-limit:] if limit else entries
