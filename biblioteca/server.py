"""FastAPI server: serves the frontend, exposes the session protocol over /ws.

Run from the project root:
    uvicorn server:app --host 127.0.0.1 --port 8000
or:
    python server.py

Set EEG_SIMULATE=1 to force the simulated EEG inlet regardless of YAML config:
    EEG_SIMULATE=1 python server.py
"""
from __future__ import annotations

import os
import traceback
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from src.config_session import SessionConfig
from src.session import SessionManager


ROOT = Path(__file__).parent
FRONTEND_DIR = ROOT / "frontend"
ASSETS_DIR = ROOT / "assets"
CONFIG_PATH = ROOT / "config" / "default.yaml"


app = FastAPI(title="Visual Imagery Neurofeedback")

# Static mounts (only if the directories exist)
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
if FRONTEND_DIR.exists():
    # /static for the JS/CSS modules; / serves index.html via the route below
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/health")
async def health():
    return {"status": "ok", "frontend_present": FRONTEND_DIR.exists()}


@app.get("/")
async def root_page():
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        return JSONResponse(
            {
                "status": "backend running, frontend not present yet",
                "websocket_url": "ws://127.0.0.1:8000/ws",
                "config_path": str(CONFIG_PATH),
                "next": "Build frontend/index.html, frontend/main.js, etc.",
            }
        )
    return FileResponse(index)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Load config fresh per connection so YAML edits during dev are picked up
    cfg = SessionConfig.from_yaml(CONFIG_PATH)
    if os.environ.get("EEG_SIMULATE") == "1":
        cfg.eeg.simulate = True

    async def send(message):
        await websocket.send_json(message)

    session = SessionManager(cfg, send)

    try:
        await session.connect()
        while True:
            msg = await websocket.receive_json()
            await session.handle(msg)
    except WebSocketDisconnect:
        print("[server] websocket disconnected")
    except Exception as e:
        traceback.print_exc()
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"server error: {type(e).__name__}: {e}",
            })
        except Exception:
            pass
    finally:
        try:
            await session.cleanup()
        except Exception as e:
            print(f"[server] cleanup error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False, log_level="info")