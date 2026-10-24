import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("ECOMARKET_FECHA_HOY", "2026-10-21")
