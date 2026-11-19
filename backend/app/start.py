"""Container entry point: fetch runtime data if needed, then serve the API.

    python -m backend.app.start
"""

from __future__ import annotations

import logging
import os

import uvicorn

from backend.app.config import get_settings
from backend.app.runtime_data import ensure_runtime_data


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    missing = ensure_runtime_data(get_settings().data_dir)
    if missing:
        logging.warning("runtime data still missing: %s", missing)
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "7860")),
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
