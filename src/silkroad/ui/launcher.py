from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    try:
        from streamlit.web import cli as stcli
    except ImportError as exc:  # pragma: no cover - handled at runtime
        raise RuntimeError("streamlit is required for the SilkRoad UI. Install with `pip install 'silkroad[ui]'`.") from exc

    script_path = Path(__file__).resolve().parent / "app.py"
    sys.argv = ["streamlit", "run", str(script_path)]
    sys.exit(stcli.main())


if __name__ == "__main__":  # pragma: no cover
    main()
