import os
import sys
import multiprocessing
import uvicorn

# PyInstaller freeze support for Windows
multiprocessing.freeze_support()

# Ensure api and root packages are resolvable
if getattr(sys, "frozen", False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from api.main import app
from api.paths import get_asset_path
import json

def get_configured_port(default_port: int = 9001) -> int:
    env_port = os.getenv("PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass

    candidate_paths = [
        get_asset_path("config.json"),
        os.path.join(os.getcwd(), "config.json"),
    ]
    for path in candidate_paths:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    val = data.get("port")
                    if val is not None:
                        return int(val)
            except Exception:
                pass
    return default_port

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = get_configured_port(9001)
    print(f"Starting Face Detection AI Engine on http://{host}:{port} ...")
    uvicorn.run(app, host=host, port=port, log_level="info")
