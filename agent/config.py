from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"
LABELS_DIR = OUTPUTS_DIR / "etiquetas"
AUDIT_LOG_FILE = OUTPUTS_DIR / "registro_acciones.jsonl"
TICKETS_FILE = OUTPUTS_DIR / "tickets_escalamiento.jsonl"

load_dotenv(BASE_DIR / ".env.local")
load_dotenv(BASE_DIR / ".env")

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
AVAILABLE_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
]

# Los pedidos son simulados con fechas fijas; "hoy" también es fijo para
# que los casos de prueba den el mismo resultado sin importar el día en
# que se corran. Se puede sobrescribir con ECOMARKET_FECHA_HOY=AAAA-MM-DD.
SIMULATED_TODAY = date.fromisoformat(os.getenv("ECOMARKET_FECHA_HOY", "2026-10-21"))

RETURN_WINDOW_DAYS = 30
LABEL_VALIDITY_DAYS = 7

# Tope de pasos del grafo por turno, para cortar bucles de herramientas.
MAX_GRAPH_STEPS = 12


def require_api_key() -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta GROQ_API_KEY. Copia .env.example a .env y pega tu key de "
            "https://console.groq.com/keys"
        )
    return api_key
