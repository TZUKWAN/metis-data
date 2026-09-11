"""Worker used by crash-recovery test: starts a streaming download, gets SIGKILLed mid-flight."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

workspace = Path(sys.argv[1])
server = sys.argv[2]

import os

os.environ.setdefault("METIS_DB_URL", "sqlite:///" + (workspace / "metis.db").as_posix())
os.environ.setdefault("METIS_WORKSPACE_DIR", str(workspace))

from app.core.config import get_settings

get_settings().ensure_dirs()
from app.db.session import init_db

init_db()
from app.downloads.service import MANAGER


async def main() -> None:
    # loop many downloads so a fast localhost server still gets killed mid-flight
    for i in range(30):
        job = MANAGER.create_job("fixture", f"big_crash_{i}", f"{server}/data/big_measurements.csv", license="CC0-1.0")
        await MANAGER.http_download(f"{server}/data/big_measurements.csv", job=job)
    print("finished (should have been killed before this)")


asyncio.run(main())
