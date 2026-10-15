# LLMs from Scratch

A from-scratch study repo for how large language models actually work, paired with a working chat you can talk to right now. The chat is deliberately **not**
a model: it is a hand-written, ELIZA-style rule engine, so the whole thing runs with no API key and no provider. Reading it end to end takes you from the
pattern-matching chatbots of the 1960s through to tokenizers, attention and training - and the `nn/` side is where the real model code gets built.

The point is the contrast. You can watch a rule engine answer (and fail to answer) in `core/rule/rules.py`, then read what a model does differently in
[docs/](./docs/README.md).

This repository contains:
- **api/**: FastAPI backend with a hand-written rule engine (`api/core/rule/rules.py`) and a placeholder `api/core/nn/` for neural-network/deep-learning code. The API exposes `reply(text, prior)` via pyRPC and serves `GET /health` with CORS.
- **web/**: Next.js 16 dark-mode chat UI that calls the API via pyRPC-generated types (`web/__pyrpc.ts`, `web/lib/pyrpc.ts`), streaming replies word-by-word.

The chat experience here is intentionally rule-based (no API key, no model provider). The docs cover the history of rule-based chatbots and the transition to LLMs.

## Quick start

### API
```bash
cd api
uv sync  # installs fastapi, pyrpc-core[fastapi], uvicorn
# create .env if needed (see api/.env.example)
uv run --env-file .env uvicorn main:app --reload --port 8000
```

Health: `http://localhost:8000/health` returns `{"status":"ok"}`.
pyRPC endpoint: `POST http://localhost:8000/rpc`.

### Web
```bash
cd web
npm install
npm run dev  # runs on http://localhost:3000
```

## Checks

```sh
cd api && uv run python -m unittest   # rule engine, nn contract, API surface
cd web && npm run lint                # eslint
cd web && npm run typecheck           # tsc --noEmit
```

These are what to run before pushing. Neither side needs an API key or a
running server.

## Docs
See [docs/README.md](./docs/README.md) for notes on rule-based chatbots, models/neural networks, transformers/attention, and the [ELIZA sources](./docs/eliza-sources.md) (papers, the MIT Press book, the recovered MAD-SLIP code) and curated resources (papers, repos, videos).

## Notes
- Regenerate pyRPC types after changing Python RPC signatures: `cd api && uv run pyrpc codegen main --client ../web`
- The rule engine is the source of truth for chat replies; `web/` does not duplicate the rule logic.
- Backend conventions and the rule-engine provenance live in [api/README.md](./api/README.md); the client's layout is in [web/README.md](./web/README.md).