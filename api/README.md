# api

FastAPI backend for the chat, exposed over [pyRPC](https://pyrpc.com) so the
Next.js client gets generated types instead of a hand-written `fetch`.

- `main.py` - the RPC surface: procedures, CORS, `/health`. No reply logic.
- `core/rule/` - the rule-based reply engine. `core/rule/rules.py` is the single
  source of truth: ordered pattern groups, per-tone replies, and the anger /
  fear / mistrust counters. See [Rule engine](#rule-engine).
- `core/nn/` - neural network / deep learning code (empty for now).
- `tests/` - backend test suite (`unittest`, no extra dependencies).

## Run

```sh
uv sync
uv run --env-file .env uvicorn main:app --reload
```

`uv run` does not load `.env` on its own, hence the flag (or export
`UV_ENV_FILE=.env`).

## Surface

Procedures are ordinary typed functions decorated with `@rpc.query` in
`main.py`:

```python
@rpc.query
def reply(text: str, prior: list[str]) -> Response:
    """Answer one message; `prior` is the thread's earlier user messages."""
    return respond(text, prior)
```

`mount_fastapi(app)` exposes them at `POST /rpc` as JSON-RPC, with schema
introspection at `GET /rpc`. `GET /health` is a plain liveness check and
`/docs` is the interactive API docs.

```
→ {"id": "1", "method": "reply", "params": ["hello", ["you are useless"]]}
← {"id": "1", "result": {"text": "Hello.", "group": "greetings",
                         "tone": "angry", "mood": {"anger": 35, ...}}}
```

Parameters are positional on the wire, which is what the generated client
sends; the reply carries the matched group, the tone and the mood counters.

## Types for the web app

`web/__pyrpc.ts` is generated from these signatures:

```sh
uv run pyrpc codegen main --client ../web
```

`web/app/api/chat/route.ts` then calls `client.reply(text, prior)` with types
derived from the Python above. Re-run codegen after changing a signature: a
stale `__pyrpc.ts` fails `npm run lint`/`tsc` loudly instead of drifting.
(`uv run pyrpc dev` regenerates on save and starts its own uvicorn.)

Note: pyRPC's codegen types list *fields* as `string[]` but list *parameters*
as `any[]`, so `prior` is only weakly typed on the client. The reply - the
direction that matters - is fully typed, including `tone` as a literal union.

## Env

`.env` is gitignored; `.env.example` is the tracked template.

| Var | Meaning |
| --- | --- |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call `POST /rpc`. The web app calls the API server-side, where CORS does not apply, so this only matters for browser callers. |

## Check

```sh
uv run python -m unittest
```

Covers the rule engine (`tests/test_rules.py`), the `core/nn` package contract
(`tests/test_nn.py`), and the FastAPI surface (`tests/test_api.py`). It runs
against the tables directly, so no server or API key is needed.

---

# Rule engine

`core/rule/rules.py` is the whole engine. Groups are checked top to bottom and
the first match wins, so the order of `GROUPS` *is* the priority.

## Mechanisms implemented

| Mechanism | Where | Provenance |
|---|---|---|
| **Ordered groups (first-match-wins)** | `GROUPS` in `rules.py` | Core ELIZA/ALICE pattern-matching philosophy. Replaces DOCTOR's keyword RANKs with a fixed decision order. |
| **Ordered priority** | Group order (threats before hostility, doubt before questions/eliza) | Our own design (PARRY-inspired: state can dominate, and safety trumps generic chit-chat). |
| **Mood/counters (anger/fear/mistrust)** | `Mood`, `apply_shift`, `tone_of` | PARRY (Colby et al. 1972), https://doi.org/10.1016/0004-3702(72)90049-5. Counters decay 10%/turn; ties resolve `angry > fear > distrustful`. |
| **Pronoun reflection** | `reflect()` + `REFLECTIONS` | DOCTOR's `post:` block, kept verbatim: `am→are`, `your→my`, `me→you`, `myself→yourself`, `yourself→myself`, `i→you`, `you→I`, `my→your`, `i'm→you are`. |
| **Synonym classes folded into patterns** | `BELIEF`, `DESIRE`, `SAD`, `HAPPY`, `FAMILY`, `EVERYONE`, `ALWAYS`, `CANNOT` | DOCTOR's `synon:` block (e.g. `belief: feel think believe wish`, `family: mother mom father ...`, `desire: want need`). |
| **Filler stripping** | `FILLER_PREFIX`, `strip_filler()` | Pragmatic - lets phrases like "ok so, what can you do?" still reach the right rule. The retry runs only when the first hit is a catch-all (`questions`/`statements`/`fallback`). |
| **Memory (thread replay)** | `MEMORY_SAVE`, `memory_line(prior)`, fallback branch in `respond()` | DOCTOR's `$` decomps stored sentences in a memory queue. Ours is stateless: if fallback hits and an earlier user line matched a saveable form (`^my\s+\w+`, `^i (feel\|am\|want\|need\|can't\|remember\|dream...)`), we answer "Earlier you said X. Tell me more about that." |
| **xnone/fallback pool** | `fallback` group | DOCTOR's `key: xnone`. We vary replies per tone and still quote the input. |
| **Initial/final** | `greetings` / `farewell` groups | DOCTOR's `initial:` / `final:` blocks. |
| **Quit words** | `farewell` / `meta` groups | DOCTOR's `quit:` (`bye`, `goodbye`, `quit`). Sessions aren't terminated here, so they stay conversational farewells / meta resets. |
| **Template reassembly** | `tail()`, `mid()`, `eliza_feeling()`, `eliza_subject()`, lambdas | DOCTOR's decomposition→reassembly. Captures are trimmed, reflected with `reflect()`, and echoed back. |
| **Clock rules** | `time` group (`today_iso()`, `now_time()`, `today_day()`) | Our addition - dynamic answers from server local time (naive). Flagged in code as a `shortcut:` (no tz/UTC). |

## Ported from the DOCTOR script (Weizenbaum 1966)

We ported the *mechanics* and every key class from the DOCTOR script. The
`eliza` group covers (in order): `i feel/felt`, `i want/need/wish/desire`,
`i am` with `@sad`/`@happy`, generic `i am`, `i can't/cannot`, `i don't`,
`i (believe/think/feel/wish/suppose/guess)`, `do you remember`,
`i remember/recollect`, `i dreamed/dreamt/dream`, bare `dream(s)`,
`you remind me of`, `you are`, `you X me`, generic `you`, `my` with `@family`,
generic `my X`, `@everyone`, `@always`, `alike/similar/same`, `because`, `if`,
`perhaps/maybe/possibly/i guess/i suppose/not sure/unsure`, `worried`,
`are you X` / `am i X`, `can you X` / `can i X`, `why don't you X` /
`why can't i X`, `i was X` / `was i X` / `was you X`, `your X` / `is your X`,
`do i feel X`, and - last, as DOCTOR's catch-all - `what X`.

### Key-by-key audit against `doctor.txt`

Verified line by line against the recovered script (`initial`/`final`/`quit`/
`pre`/`post`/`synon` + 37 keys). "Where" is the group that answers it here.

| DOCTOR key | Where here | Notes |
| --- | --- | --- |
| `xnone` | `fallback` | Reply pool kept, per-tone. |
| `sorry`, `apologise` | `apology` | `apologise` → `sorry` is the same group. |
| `remember` (also `do you remember`) | `eliza` | Both decomp forms. |
| `if` | `eliza` | |
| `dreamed` / `dream` | `eliza` | `goto dream` is the bare `dream` pattern, not a jump. |
| `perhaps` | `eliza` | Pool kept. |
| `name` | `identity` | Owned by our identity group; DOCTOR's "not interested in names" is not a fit here. |
| `deutsch`/`francais`/`italiano`/`espanol`, `xforeign` | - | Omitted: English-only, same as DOCTOR's own `xforeign` line. |
| `hello` | `greetings` | |
| `computer` | `project`, `capabilities`, `how-it-works` | Split by question, not one pool. |
| `am` | `eliza` | `am i X` only; bare "am" omitted (see below). |
| `are` | `eliza` | `are you X`; the generic `* are *` form is omitted (see below). |
| `your` | `eliza` | |
| `was` | `eliza` | All three: `was i X`, `i was X`, `was you X`. |
| `i` | `eliza` | `@desire`, `i am @sad`, `i am @happy`, eager `i am`, `i @cannot`, `i don't`, `do i feel`, `i @belief ... i`, `i am`; the bare `*` decomp is `statements`. |
| `you` | `eliza` | `you remind me of` → `alike`, `you are`, `you X me`, generic `you`. |
| `yes` / `no` | `yesno` | |
| `my` (incl. `$` memory decomp) | `eliza` + memory hook | Memory is derived from the thread, not stored. |
| `can` | `eliza` | `can you X`, `can i X` - DOCTOR's reassembly text is swapped relative to its decomp; ours follows the decomp. |
| `what` | `eliza` (last) | Catches what-questions nothing above claims. |
| `because` | `eliza` | |
| `why` | `eliza` | `why don't you X`, `why can't i X`; bare `why` omitted (see below). |
| `everyone`, `everybody`, `nobody`, `noone` | `eliza` | One `EVERYONE` class. |
| `always` | `eliza` | |
| `alike`, `like` | `eliza` | `like` arrives via the `alike` pattern. |

### Deliberate deviations

All documented so the port stays auditable:

- **`goto` and numeric ranks.** DOCTOR marks keys `key: name N` and jumps
  between them with `goto`. Here the rank is the position in `GROUPS` and a
  `goto` target is either a group below or a standalone pattern (`goto alike`,
  `goto what`, `goto dream` are the `alike`, `what`, `dream` patterns).
- **Bare `what` vs `how`/`when`.** DOCTOR's `pre: how what` / `pre: when what`
  fold every how- and when-question into the `what` key. We only port bare
  `what`; `how`/`when` questions fall to `questions` so they get the honest
  "I don't know that one" answer rather than a deflection. Same for bare `why`.
- **Bare `am` and the generic `* are *` decomp.** Omitted: "Why do you say
  'am'?" and "Did you think they might not be X?" need DOCTOR's `(2)` capture
  from a sentence we don't otherwise claim.
- **`pre:` / `post:` block.** The `post:` pairs are `REFLECTIONS`, kept verbatim
  - including the one-way `am → are` and `you → I`, which is why DOCTOR's own
  reassembly produces "Have you ever dreamed about I before?". That awkwardness
  is faithful, so it stays. Two `pre:` contractions are applied in `normalize()`
  (`i'm → i am`, `you're → you are`) because our patterns are anchored with `^`
  and DOCTOR matches a key anywhere in the sentence; the rest
  (`recollect→remember`, `dreamt→dreamed`, `same→alike`, `cant→can't`,
  `dont→don't`) are folded into the regex alternations instead.
- **Key ranking is a flat order.** DOCTOR sorts keys by weight and, for equal
  weights, by where the word appears in the sentence. We approximate with one
  group order plus two guards: `QUESTION_KEYS` keeps the low-ranked question
  keys (`are you`, `can you`, `why don't you`, …) from being stolen by the
  `you X me` reflection, and `NOT_QUESTION` keeps loose keywords (`dream`, `if`,
  `because`, `everyone`, `always`, `alike`, `worried`) from stealing real
  questions.
- **`yes`/`no` fire mid-sentence** (DOCTOR matches the word anywhere):
  "no there's nothing to tell" reaches the `no` pool. We also tolerate repeated
  letters (`nooo`) and "cut it offf", which DOCTOR's exact word match would miss.

### Worked example: the same troll lines through both engines

Run against the recovered `doctor.txt` with `wadetb/eliza`'s interpreter, next
to this engine:

| input | real DOCTOR | here |
| --- | --- | --- |
| `helloo` | `I'm not sure I understand you fully.` (xnone - "helloo" is not the word `hello`) | `Hellooo. What can I do?` (greetings; deliberate) |
| `no there's nothing to tell` | `Are you saying no just to be negative?` | same pool (`yesno`) |
| `i won't` | `You say you won't ?` | "You say you won't?" (same family) |
| `no` | `You are being a bit negative.` | same pool (`yesno`) |
| `are you playing with me` | `Why are you interested in whether I am playing with you or not ?` | same line (`eliza`, key `are`) |
| `okay now you're trolling` | `What makes you think I am trolling ?` | same line (`eliza`, via `pre: you're you are`) |
| `nooo, cut it offf` | `Do you feel strongly about discussing such things ?` (xnone) | `threats` group - shutdowns are ours, not DOCTOR's |
| `i'm trying to do a project` | key `i`, eager `i am` | same (`eliza`) |

The one intentional difference is that DOCTOR has no shutdown key at all;
`cut it off` is our own `threats` group.

## How to add a rule

1. Put it in the **right group** - match what it is conceptually, before more
   generic groups below it.
2. If it should shift mood, set `shift={...}` on the `Group` or the `Pattern`.
3. For each tone you want to answer differently, supply a
   `str` / `list[str]` / `Callable[[Mood, str], str]`. Missing tones fall back to
   `"calm"`.
4. Run `uv run python -m unittest`.
5. To reflect pronouns use `reflect()` and take captures with
   `tail()` / `mid()` / `word_in()` - never a manual string replace.

## Notes

- The memory mechanism is **derived from the thread** (`prior`), not stored
  between sessions; that's intentional.
- The clock is **naive local time** (server-side), flagged in code with
  `shortcut: ... add tz/UTC when clients span zones.`
- `statements` matches any multi-word line with no sentence-final `? ! .`, so
  plain declaratives like `i like trains` are acknowledged, not shrugged at.
- Small talk (`nothing much`, `not much`, `the usual`, ...) lands in the
  dedicated `smalltalk` group before `questions`/`statements`/`fallback`.
- The `fallback` and `questions` pools are written for a visitor, not a
  contributor: they vary, stay honest about not knowing, and never say "rule
  table", "add a pattern" or name a file. `**help**` is the one affordance they
  point at.

## Provenance (sources)

- Weizenbaum, J. (1966). *ELIZA - A computer program for the study of natural
  language communication between man and machine.* *Communications of the ACM*
  9(1):36-45. https://doi.org/10.1145/365153.365168
- DOCTOR script: the recovered MAD-SLIP ELIZA (Weizenbaum, MIT 1965-66),
  curated at https://elizagen.org (Original ELIZA), with Anthony Hay's
  transcription/annotation. Also mirrored at
  https://github.com/critical-code-studies/ELIZA.
- Browser re-implementation for structure: https://elizaemulator.com
  (pipeline + reflections + rule topics).
- PARRY (state/mood): Colby, K. M. et al. (1972). *Turing-like
  indistinguishability tests for the validation of a computer simulation of
  paranoid processes.* *Artificial Intelligence* 3:199-221.
  https://doi.org/10.1016/0004-3702(72)90049-5
- ALICE/AIML influence on ordered categories (not a direct port). AIML 1.0.
- Deep dive: *Inventing ELIZA: How the First Chatbot Shaped the Future of AI*
  (Ciston et al., 2026), MIT Press. https://findingeliza.org ·
  https://mitpress.mit.edu/9780262052481/inventing-eliza/
- ELIZA effect + history: [docs/eliza-sources.md](../docs/eliza-sources.md)
  and [docs/01-rule-based-chatbots.md](../docs/01-rule-based-chatbots.md)

---

## Standards

Written down here so there is no separate style doc.

**Layout.** `main.py` is the API surface only - procedures, CORS, `/health`; no
reply logic. Reply logic lives in `core/rule/`. Model code goes in `core/nn/`;
nothing rule-related may move there. One concern per file.

**Rule tables.** Position *is* the priority: no numeric weights, specific
groups above generic ones. Every pattern needs a `"calm"` reply. Reflect
pronouns with `reflect()`, capture with `tail()`/`mid()`. Moods are data, not
state - `respond(text, prior)` replays the thread. Details in
[Rule engine](#rule-engine).

**Python.** Type hints on every signature. Standard library first; the runtime
deps are FastAPI, pyRPC and uvicorn and nothing else. No bare `except`. Comments
explain *why*, one line. A deliberate limit gets
`shortcut: <the limit>, <when to upgrade>` (see the clock rules in `rules.py`).

**Tests.** Stdlib `unittest`, no fixtures, no server. New rule → assert the
**group name**, not the exact wording (replies are picked at random, so
exact-text assertions flake). New mechanism → a focused test class. Bug report →
reproduce it as a transcript test first, then fix the rule.

**API surface.** Procedures are flat, ordered, positional parameters. Changing a
signature means re-running codegen; a stale `web/__pyrpc.ts` then fails `tsc` in
the web app. Keep the reply field names (`text`, `group`, `tone`, `mood`)
stable. `/health` must stay dependency-free so it answers while the rules are
being edited. Config comes from the environment and is documented in
`.env.example`; never hard-code an origin.

**When you change something.** Rule edited → run the tests. RPC signature changed
→ codegen, then `tsc` in `web/`. New limit shipped → leave a `shortcut:`
comment. Surprising-but-deliberate behaviour → a `note` on the group and a line
in the Rule engine section above.
