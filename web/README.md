# web

The chat UI: a dark-mode [Next.js](https://nextjs.org) 16 app built on
[assistant-ui](https://www.assistant-ui.com/) components and shadcn/ui styling.
It holds no reply logic - every answer comes from the FastAPI backend in
`../api`.

- `app/assistant.tsx` - the chat runtime and sidebar/main-pane layout.
- `app/api/chat/route.ts` - the only place the browser talks to the backend:
  it calls `client.reply(text, prior)` and streams the reply back word by word.
- `lib/pyrpc.ts` - the pyRPC client. Types come from `__pyrpc.ts`, which is
  generated from the Python signatures.
- `components/ui/` and `components/assistant-ui/` - vendored kits, kept as
  upstream ships them (see the lint override in `eslint.config.mjs`).

## Run

The backend must be running first (see `../api/README.md`).

```sh
npm install
npm run dev
```

Open http://localhost:3000. `API_URL` points at the backend; copy
`.env.example` to `.env.local` to change it (default `http://127.0.0.1:8000`).

If the backend is not running, the chat still loads and the reply says so.

## Checks

```sh
npm run lint       # eslint
npm run typecheck  # tsc --noEmit
npm run build      # production build
```

## Generated types

`__pyrpc.ts` is generated, not hand-written:

```sh
cd ../api && uv run pyrpc codegen main --client ../web
```

A stale file fails `npm run typecheck`, so a renamed field in the Python
surface cannot silently drift.

## Notes

- Replies are streamed in the route handler at ~20ms per word so the answer
  arrives the way a model would type it. There is no model - see `../api`.
- Threads live in the browser tab only; there is no database.
