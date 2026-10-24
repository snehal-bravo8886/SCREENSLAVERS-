"""Minimal service scaffold. No investigation or dataset API is wired yet."""
from fastapi import FastAPI

app = FastAPI(title="Screenslavers - WIP scaffold", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "screenslavers-scaffold", "connected_to_frontend": False}
