# Rule-based chatbots: from Turing to SmarterChild

The key distinction is mechanism. Early chatbots didn't "understand"; they were pattern-matching systems with hand-written rules. The jump from that to LLMs is not a better chatbot - it's a different approach entirely.

## A timeline (core ideas)
1. **Turing, 1950 - "Computing Machinery and Intelligence" (Mind)**: Introduced the Imitation Game (Turing test). The question was behavioral: can a machine be indistinguishable from a human in conversation? (Turing 1950) https://doi.org/10.1093/mind/LIX.236.433

2. **Weizenbaum, 1966 - ELIZA (MIT)**: ELIZA simulated a Rogerian/psychotherapist by applying simple pattern matching. The program looked for keywords/phrases in user text and responded using templated transformations; it had no understanding whatsoever. This is the canonical example of a rule/script-based system. (Weizenbaum 1966) https://doi.org/10.1145/365153.365168 - primary sources (the papers, the MIT Press book *Inventing ELIZA*, the MAD-SLIP code recovered from Weizenbaum's MIT archive in 2021, and the ELIZA effect) are in [ELIZA: the paper, the book, the code, and the effect](./eliza-sources.md).

3. **Colby et al., 1972 - PARRY (Stanford)**: A rule-based program simulating a paranoid schizophrenia patient. Importantly, PARRY incorporated internal states (e.g., anger, fear, mistrust) that shifted its responses over time - it didn't just match patterns, it carried mood/state. (Colby et al. 1972) https://doi.org/10.1016/0004-3702(72)90049-5. Famously, ELIZA and PARRY were connected in an early experiment where one chatbot conversed with the other (often cited in discussions of early "chatbot meets chatbot" trials).

4. **ALICE, ~1995 - AIML**: ALICE (Artificial Linguistic Internet Computer Entity) used AIML (Artificial Intelligence Markup Language), a rule/template system with thousands of category patterns. The classic figure cited is around 41,000 hand-written patterns at scale. ALICE proved rule-based systems could handle a lot of surface variation while still being entirely hand-scripted.

5. **SmarterChild, 2001 - AOL Instant Messenger (ActiveBuddy)**: One of the earliest "do everything" chatbots on a mainstream messaging platform. Often viewed as a precursor to later assistants, it was still fundamentally rule/script/template-driven, not a generative model trained on massive text corpora.

## The black box: input → process → output
It's useful to abstract a chatbot as a black box: input comes in, some process runs, output comes out. In rule-based systems the process is "run the input through a set of if-statements and pattern rules to pick a response." The UI (input box, messages, conversation thread) is structurally the same as modern chat UIs; the replacement is swapping that rule-based process for an LLM that maps prompt → completion. In this framing, different mechanisms implement the same conversational interface.

## How rule-based systems actually work (in practice)
- **Normalization**: lowercase, collapse whitespace, strip punctuation as needed.
- **Ordered matching**: patterns are checked in priority order; the first matching pattern wins (decision tree).
- **State/mood**: systems like PARRY showed the value of internal counters (anger/fear/mistrust) that decay over time and influence tone/choice of responses.
- **Templates and variation**: to avoid repetition, rules may offer multiple variants per tone or pick randomly from pools.
- **Explicit coverage**: humans must anticipate and write rules for cases; unmatched input falls to a fallback.

## This repository as a live example
`api/core/rule/rules.py` is exactly this kind of rule-based system: ordered groups, regex patterns, per-tone replies, mood shifts that carry over the conversation thread, and randomized fallback pools. There is no model provider and no API key - every response comes from hand-written patterns. That makes the mechanism explicit and easy to audit.

ELIZA's own moves are ported straight in: the `eliza` group reflects `i feel X` back as *"Why do you feel X?"* and `my dog is sick` as *"Tell me more about your dog."*, with the classical continuations ("Please go on.", "How does that make you feel?") in the statements pool - the same logic as the small TypeScript chatbot shipped with the Syntax video's companion repo. Two modern additions sit alongside it: leading small talk is stripped when a message would otherwise miss every rule (`okay what can you do?` still reaches the capabilities rule), and the `time` group answers date/time questions by reading the server clock, so a hand-written rule can carry a live value.

## Why the jump to LLMs is different
Rule-based systems encode answers by hand. LLMs (e.g., GPT = Generative Pre-trained Transformer) are trained on data to predict next tokens, producing outputs probabilistically. The shift is from *programmed responses* to *learned sequence prediction* - same I/O surface, fundamentally different process. That distinction is the point of the user transcript: before diving into LLMs, it's instructive to see how ELIZA-like systems work.