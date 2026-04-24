import sys
from pathlib import Path

_shared = Path(__file__).resolve().parent.parent / "shared"
if _shared.is_dir() and str(_shared) not in sys.path:
    sys.path.insert(0, str(_shared))
