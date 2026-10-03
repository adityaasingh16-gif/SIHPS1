"""Optional Ollama-compatible localhost passthrough; contains no hosted API client."""

import json
import os
import urllib.error
import urllib.request

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
DEFAULT_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1")
DEFAULT_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
REQUEST_TIMEOUT = max(1.0, float(os.getenv("OLLAMA_PROXY_TIMEOUT_SECONDS", "45")))
app = FastAPI(title="Local Ollama Proxy")


def _forward(path: str, body: dict | None = None) -> dict:
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}{path}", data=payload,
        headers={"Content-Type": "application/json"} if payload is not None else {},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read())


@app.get("/health")
async def health():
    try:
        await run_in_threadpool(_forward, "/api/tags")
        return {"status": "ok", "provider": "local"}
    except Exception as exc:
        return JSONResponse({"status": "offline", "provider": "local", "detail": str(exc)}, status_code=503)


@app.get("/api/version")
async def version():
    return {"version": "local-ollama-proxy"}


@app.get("/api/tags")
async def tags():
    try:
        return await run_in_threadpool(_forward, "/api/tags")
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)


@app.get("/api/available-models")
async def available_models():
    return {"chat_models": [DEFAULT_CHAT_MODEL], "embedding_model": DEFAULT_EMBED_MODEL}


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    body.setdefault("model", DEFAULT_CHAT_MODEL)
    try:
        result = await run_in_threadpool(_forward, "/api/chat", body)
        return JSONResponse(result)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return JSONResponse({"error": f"Local Ollama request failed: {exc}"}, status_code=502)


@app.post("/api/embeddings")
async def embeddings(request: Request):
    body = await request.json()
    body.setdefault("model", DEFAULT_EMBED_MODEL)
    try:
        return JSONResponse(await run_in_threadpool(_forward, "/api/embeddings", body))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return JSONResponse({"error": f"Local Ollama embedding failed: {exc}"}, status_code=502)


@app.post("/api/embed")
async def embed(request: Request):
    body = await request.json()
    body.setdefault("model", DEFAULT_EMBED_MODEL)
    try:
        return JSONResponse(await run_in_threadpool(_forward, "/api/embed", body))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return JSONResponse({"error": f"Local Ollama embedding failed: {exc}"}, status_code=502)
