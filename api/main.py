"""FastAPI server for the rule-based chat, exposed over pyRPC.

Run: `uv run --env-file .env uvicorn main:app --reload`
Regenerate the client types: `uv run pyrpc codegen main --client ../web`

The procedures are the API. The types the Next.js client sees are generated
from these signatures, so a field renamed here is a compile error there.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyrpc_core import rpc
from pyrpc_fastapi import mount_fastapi

from core.rule import Response, respond

app = FastAPI(title="LLMs from Scratch API")

# Only needed if something calls /rpc from a browser; the Next.js route handler
# in web/ calls it server-side, where CORS does not apply.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Plain liveness check, outside the RPC surface."""
    return {"status": "ok"}


@rpc.query
def reply(text: str, prior: list[str]) -> Response:
    """Answer one message. `prior` is the thread's earlier user messages,
    replayed so the mood carries over between turns."""
    return respond(text, prior)


mount_fastapi(app)
