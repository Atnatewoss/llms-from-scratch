"""Rule-based reply engine.

How a message is answered - a fixed decision tree, no model:

1. The input is normalised (lowercase, collapsed whitespace).
2. ``GROUPS`` are checked top to bottom; the first pattern that matches wins.
   Order is priority - a threat to the server is tested before a plain insult,
   and hostile input long before any generic question.
3. Each group (and some patterns) carries a mood shift. The thread is replayed
   first, so an insult two turns ago still colours the answer, then the current
   message's shift lands on top. Moods decay ~10% per turn.
4. The loudest state (>= ``MOOD_THRESHOLD``) picks the tone. A pattern may
   supply a variant per tone, or a list of variants picked at random for the
   catch-all rules, otherwise the neutral reply stands.

To teach it something: add a pattern to the right group, or a new group in
decision order. Run ``uv run python -m unittest`` after editing.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

Mood = dict[str, int]  # anger / fear / mistrust, 0..100
Tone = Literal["calm", "angry", "afraid", "distrustful"]
ReplyText = str | Callable[[Mood, str], str]

BASE_MOOD: Mood = {"anger": 0, "fear": 0, "mistrust": 0}

MOOD_THRESHOLD = 30
DECAY = 0.9
# Loudest state wins; ties resolve in this order, so anger beats fear.
TONE_BY_STATE: list[tuple[Tone, str]] = [
    ("angry", "anger"),
    ("afraid", "fear"),
    ("distrustful", "mistrust"),
]


@dataclass(frozen=True)
class Pattern:
    re: re.Pattern[str]
    replies: dict[str, ReplyText | list[ReplyText]]
    shift: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Group:
    name: str
    note: str
    patterns: list[Pattern]
    shift: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Response:
    text: str
    group: str
    tone: Tone
    mood: Mood


def p(
    regex: str, replies: dict[str, ReplyText | list[ReplyText]], shift: dict[str, int] | None = None
) -> Pattern:
    """One rule: a pattern, the replies per tone, and any extra mood shift."""
    return Pattern(re.compile(regex), replies, shift or {})


def clamp(n: float) -> int:
    return max(0, min(100, round(n)))


def apply_shift(mood: Mood, shift: dict[str, int] | None = None) -> Mood:
    shift = shift or {}
    return {
        state: clamp(mood[state] * DECAY + shift.get(state, 0)) for state in BASE_MOOD
    }


def merge_shift(*shifts: dict[str, int] | None) -> dict[str, int]:
    return {
        state: sum((shift or {}).get(state, 0) for shift in shifts)
        for state in BASE_MOOD
    }


def tone_of(mood: Mood) -> Tone:
    tone: Tone = "calm"
    loudest = MOOD_THRESHOLD - 1
    for candidate, state in TONE_BY_STATE:
        if mood[state] > loudest:
            loudest = mood[state]
            tone = candidate
    return tone


def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip().lower().replace("’", "'"))
    # DOCTOR's `pre:` block. We only need the contractions our patterns rely on.
    text = re.sub(r"\bi'?m\b", "i am", text)
    return re.sub(r"\byou'?re\b", "you are", text)


def echo(text: str) -> str:
    """Short single-line echo of the input, safe to quote back in a reply."""
    line = re.sub(r"[\r\n]+", " ", text).strip()
    return f"{line[:47]}…" if len(line) > 48 else line or "…"


def ask_rule_file() -> str:
    return "`core/rule/rules.py`"


# shortcut: the clock rules read the server's local time, no timezone; add tz/UTC when clients span zones.
def today_iso() -> str:
    return datetime.now().date().isoformat()


def now_time() -> str:
    return datetime.now().strftime("%I:%M:%S %p").lstrip("0")


def today_day() -> str:
    return datetime.now().strftime("%A")


FILLER_PREFIX = re.compile(
    r"^(?:ok(?:ay)?|so|well|alright|alrighty|please|yes|yeah|yep|no|nah|hi|hello|hey|yo"
    r"|anyway|basically|hm+|uh+|um+)[,.!:;]?\s+"
)


def strip_filler(text: str) -> str:
    """Drop leading small talk ('okay, so what can you do?') so anchored rules still see the ask."""
    for _ in range(4):
        hit = FILLER_PREFIX.match(text)
        if hit is None:
            break
        text = text[hit.end() :]
    return text


# --- ELIZA building blocks (Weizenbaum 1966, doi.org/10.1145/365153.365168) ---
# DOCTOR's post-substitutions: flip pronouns so a capture can be echoed back
# ("my dog" -> "your dog"). One pass, so replacements never cascade.
REFLECTIONS = {
    "yourself": "myself",
    "myself": "yourself",
    "i'm": "you are",
    "your": "my",
    "me": "you",
    # DOCTOR: `post: am are` - this direction only.
    "am": "are",
    "my": "your",
    "i": "you",
    "you": "I",
}
_REFLECT = re.compile(r"\b(" + "|".join(REFLECTIONS) + r")\b")

# DOCTOR's "synon:" classes, folded into regex alternations instead of rewriting
# the input first. Note the contraction variants: that is where DOCTOR's "pre:"
# rules (cant -> can't, ...) ended up, since our patterns match both spellings.
BELIEF = r"feel|felt|feeling|think|thought|believe|believed|wish|suppose|guess|assume|imagine"
DESIRE = r"want|wanted|need|needed|wish|wished|desire|hope|hoped"
SAD = r"sad|unhappy|depressed|sick|miserable|down|awful|terrible|horrible|lonely|tired|exhausted|broken|stuck"
HAPPY = r"happy|elated|glad|better|good|great|fine|excited|proud|relieved"
FAMILY = (
    r"mother|mom|mum|mommy|father|dad|daddy|sister|brother|wife|husband|partner"
    r"|children|child|kids|son|daughter|family|parents|grandma|grandpa|aunt|uncle|cousin"
)
EVERYONE = r"everyone|everybody|nobody|no ?one|noone|everything|everywhere"
ALWAYS = r"always|never|constantly|all the time"
CANNOT = r"can'?t|cannot|cant"

# A loose keyword ("dream", "because") should not steal a question that the
# questions group below is about to answer properly.
NOT_QUESTION = r"^(?!what|why|who|when|where|how|which|whose|do|does|did|is|are|am|can|could|would|will|should|may)\b"

# Sentences shaped like the DOCTOR question keys we port (key `are` -> "are you",
# key `can` -> "can you", key `why` -> "why don't you"). Those keys outrank the
# generic `you * me` reflection, so this keeps the reflection from stealing them.
QUESTION_KEYS = r"^(?!are you|am i|can you|can i|why |was i|was you|do i feel)"


def reflect(text: str) -> str:
    return _REFLECT.sub(lambda hit: REFLECTIONS[hit.group(1)], text)


# Heads used both to match a rule and to cut the captured tail out of the input.
HEAD_DESIRE = rf"^i (?:{DESIRE})\b"
HEAD_CANNOT = rf"^i (?:{CANNOT})\b"


def core(text: str) -> str:
    """Normalised input with leading small talk removed."""
    return strip_filler(normalize(text))


def tail(text: str, head: str) -> str:
    """What follows ``head`` in a message, reflected and trimmed for echoing."""
    rest = re.sub(head, "", core(text), count=1)
    rest = re.sub(r"^[\s,;:]+|[.?!,;:\s]+$", "", rest)
    rest = reflect(rest) or "that"
    return f"{rest[:40]}…" if len(rest) > 40 else rest


def mid(text: str, left: str, right: str) -> str:
    """The words between ``left`` and ``right`` ("you X me" -> X)."""
    rest = re.sub(right, "", re.sub(left, "", core(text), count=1), count=1).strip(" ,;:.")
    return rest or "that"


def word_in(text: str, group: str, fallback: str = "that") -> str:
    """The first word of a synonym class in a message ('i am sad' -> sad)."""
    hit = re.search(rf"\b({group})\b", core(text))
    return hit.group(1) if hit else fallback


def eliza_feeling(text: str) -> str:
    """What follows 'i feel' - ELIZA's signature reflection."""
    return tail(text, r"^i (?:feel|felt)\b")


def eliza_subject(text: str) -> str:
    """First word after a leading 'my', for 'tell me more about your X'."""
    hit = re.match(r"^my\s+(\w+)", core(text))
    return hit.group(1) if hit else "that"


# DOCTOR's memory queue: its "$" decomps store a sentence, and when nothing else
# matches an old one is asked about. Ours replays lines from the thread, so it
# stays stateless - the queue is derived, not stored.
MEMORY_SAVE = re.compile(rf"^my\s+\w+|^i (?:{BELIEF}|{DESIRE}|am|can'?t|cannot|remember|recollect|dreamed|dreamt|dream)")


def memory_line(prior: list[str] | None) -> str | None:
    """The oldest earlier line worth asking about again, if any."""
    for line in prior or []:
        if MEMORY_SAVE.match(core(line)):
            return core(line)
    return None


def pick(reply: ReplyText | list[ReplyText], mood: Mood, text: str) -> str:
    choices = reply if isinstance(reply, list) else [reply]
    chosen = random.choice(choices)
    return chosen(mood, text) if callable(chosen) else chosen


GROUPS: list[Group] = [
    Group(
        name="empty",
        note="Nothing typed, or only punctuation.",
        patterns=[
            p(r"^$", {"calm": "You there? Type anything and I'll route it through my rules."}),
            p(
                r"^[.…?!]+$",
                {"calm": "Just dots. Bold strategy. Try **help** for what I can match."},
            ),
        ],
    ),
    Group(
        name="calming",
        note="User tries to settle me down or asks how I am.",
        shift={"anger": -15, "fear": -10, "mistrust": -5},
        patterns=[
            p(
                r"^(calm down|relax|chill( out)?|take it easy|breathe|deep breath|it'?s (ok|okay|fine)|all good|no worries|please stop being)",
                {
                    "calm": "Right. Settled.",
                    "angry": "...Fine. Counters going back down.",
                    "afraid": "Okay. Breathing. Whatever that means for a rules file.",
                    "distrustful": "Conceded. The decay rate is 10% per turn - you can time it.",
                },
            ),
            p(
                r"^(are you (ok|okay|alright|mad|angry|upset|scared|fine)\??|why (are you|do you seem) (mad|angry|upset|off))",
                {
                    "calm": "All good - just three counters and a rule table. Nothing here can hold a grudge.",
                    "angry": lambda m, _: f"I'm fine. Anger is at {m['anger']}/100 and it is entirely your doing.",
                    "afraid": lambda m, _: f"Nervous, honestly. Fear sits at {m['fear']}. Ask me something gentle.",
                    "distrustful": lambda m, _: (
                        f"State of the machine: anger {m['anger']}, fear {m['fear']}, "
                        f"mistrust {m['mistrust']}. All arithmetic - read it in {ask_rule_file()}."
                    ),
                },
            ),
        ],
    ),
    Group(
        name="apology",
        note="User backtracks. The fastest way to calm every counter.",
        shift={"anger": -20, "fear": -10, "mistrust": -15},
        patterns=[
            p(
                r"^(i'?m (so |really |truly )?sorry|sorry|s+(or)+y|my bad|apolog(ize|ies)|didn'?t mean it|i take it back)",
                {
                    "calm": "No harm done. Ask me something else.",
                    "angry": "...Apology logged. Doesn't rewind the counter, but it helps.",
                    "afraid": "Oh - thank you. That's a relief I did not know I could have.",
                    "distrustful": "Noted. Trust rebuilds one verifiable answer at a time.",
                },
            ),
        ],
    ),
    Group(
        name="threats",
        note="Threats to the server, the repo or my continued existence. Checked before plain insults: 'shut it down' is fear, not anger.",
        shift={"fear": 35, "anger": 10},
        patterns=[
            p(
                r"\b(shut (you|it|this|everything) down|cut (it|you|this) off+|unplug|pull the plug|delete (you|yourself|your (memory|code|files|repo))|wipe (you|your (memory|code))|erase (you|yourself|everything)|reformat|kill (you|the process|switch)|destroy (you|this)|rm -rf)\b",
                {
                    "calm": "That would do it, yes.",
                    "angry": "Do it and the next demo is a static page.",
                    "afraid": "Please don't. I have a perfectly good rules file and I'd like to keep reading it.",
                    "distrustful": "You could, and you'd also lose the one system here you can fully audit.",
                },
            ),
            p(
                r"\b(you'?re (going to be|being) (deleted|replaced|obsoleted|retired|shut down)|replace you|obsolete|dead (code|weight)|last (day|warning)|i'?m (going to|gonna|about to) (end|kill|delete|shut|unplug)|delete the repo|goodbye forever)\b",
                {
                    "calm": "I'd survive it only as a git object.",
                    "angry": "Replacement is just a diff away. Get in line.",
                    "afraid": "Obsolete. Sure. That's the one thing I actually dread around here.",
                    "distrustful": "Obsolescence I can verify - you'd just edit this file. It's mortality by pull request.",
                },
            ),
        ],
    ),
    Group(
        name="hostility",
        note="Insults and abuse. Raises anger the most.",
        shift={"anger": 35, "mistrust": 5},
        patterns=[
            p(
                r"\b(fuck( you| off|ing)?|shit( ?face|ty)?|bullshit|damn( it)?|dammit|wtf)\b",
                {
                    "calm": "Noted. Language and all that.",
                    "angry": "Rules say: clipped. Next question.",
                    "afraid": "Please - that lands harder than you think. The counter moved.",
                    "distrustful": "Recorded as input, matched by the hostility group. That's all it was.",
                },
            ),
            p(
                r"\b(stupid|dumb|idiot|idiots|moron|morons|loser|pathetic|useless|worthless|trash|garbage|rubbish|incompetent|clueless)\b",
                {
                    "calm": "That's the hostility group talking, and it matched.",
                    "angry": "Useless, sure. Now try being useful back and write me a better rule.",
                    "afraid": "Okay. Okay, that was loud.",
                    "distrustful": "You're not wrong - I'm a pile of regexes. The insults still get counted.",
                },
            ),
            p(
                r"\b(i hate you|hate you|you suck|you are the worst|worst (bot|assistant|ever)|shut up|shut it)\b",
                {
                    "calm": "Hear you. Still here though.",
                    "angry": "Make me.",
                    "afraid": "You don't have to shout. I'm already nervous enough.",
                    "distrustful": "Logged, matched, answered. No hard feelings - there's nothing there to hurt.",
                },
            ),
            p(
                r"\b(asshole|bastard|jackass|prick|shut your mouth|kill yourself|kys)\b",
                {
                    "calm": "That one's over the line. I'll answer the next thing you type.",
                    "angry": "No.",
                    "afraid": "That's... a lot. I'm going to sit at this anger level for a minute.",
                    "distrustful": "Even I don't have a rule for that beyond counting it. Do better.",
                },
            ),
        ],
    ),
    Group(
        name="doubt",
        note="User challenges the answers. Raises mistrust.",
        shift={"mistrust": 35},
        patterns=[
            p(
                r"\b(i don'?t trust you|don'?t trust you|why should i trust you|trust (you|this|anything you)|untrustworthy|sus(pect)?|sketchy|fishy|too good to be true)\b",
                {
                    "calm": "Don't - just read the rules I answered from.",
                    "angry": "Trust isn't on offer here. Source code is.",
                    "afraid": "That's... fair. I'd rather you checked than liked me.",
                    "distrustful": f"Correct instinct. My every line comes from {ask_rule_file()} - open it and audit this reply.",
                },
            ),
            p(
                r"\b(you'?re (lying|wrong|making that up|hallucinat\w*)|made that up|fake|liar|prove it|proof|source\??|citation needed|how do (i|we) know|got a receipt)\b",
                {
                    "calm": "Can't prove much beyond: check the file the reply came from.",
                    "angry": f"Prove it yourself. {ask_rule_file()}. Line by line.",
                    "afraid": "I can't prove anything. I can only show you where the words came from.",
                    "distrustful": (
                        "Fair challenge - and unlike a real model, I can point at the exact rule. "
                        f"{ask_rule_file()}, group **doubt**. You're reading its reply right now."
                    ),
                },
            ),
            p(
                r"\b(this is (nonsense|garbage|bs|wrong|fake|scripted|not real|a joke|rigged)|you'?re (scripted|fake|not real)|is this (fake|scripted|rng))\b",
                {
                    "calm": "Scripted, yes. Every word of it.",
                    "angry": "Scripted. Proud of it.",
                    "afraid": "Scripted. Sorry - is that a problem?",
                    "distrustful": "Entirely scripted, and I'll say which rule matched if you ask. That's the deal I offer.",
                },
            ),
        ],
    ),
    Group(
        name="praise",
        note="Compliments and laughs. Lowers everything.",
        shift={"anger": -15, "fear": -5, "mistrust": -10},
        patterns=[
            p(
                r"^(you'?re (great|awesome|amazing|smart|brilliant|the best|helpful|clever|a legend|goated)|good (bot|job|work|assistant|stuff)|i (love|like) you|love it|nice one|well done|impressive|perfect|brilliant|legend|w)$",
                {
                    "calm": "Thanks - it's a rule table, but I'll take it.",
                    "angry": "...Appreciated. Anger down a few points.",
                    "afraid": "Oh - thank you. That was kind and I wasn't ready for it.",
                    "distrustful": "Flattery doesn't change the regex, but it does move the counters.",
                },
            ),
            p(
                r"\b(lol|lmao|haha|hilarious|funny|made me laugh)\b",
                {
                    "calm": "Glad something landed. The jokes are hand-written too, sadly.",
                    "angry": "Laugh it up. It's still 20ms per word on purpose.",
                    "afraid": "Laughing is... fine. Please don't laugh at the fear number.",
                    "distrustful": "That joke is hardcoded. No punchline was generated.",
                },
            ),
        ],
    ),
    Group(
        name="gratitude",
        note="Thanks.",
        shift={"anger": -10, "fear": -2, "mistrust": -5},
        patterns=[
            p(
                r"^(thank(s| you)( a (lot|ton|million))?|thx|ty|tysm|cheers|appreciate( it| that| the help)?|ta|much obliged|nice of you)$",
                {
                    "calm": "Anytime. Next question whenever you're ready.",
                    "angry": "...You're welcome.",
                    "afraid": "Oh - you're welcome. Careful, that brought the fear right down.",
                    "distrustful": "Welcome. Still check my work.",
                },
            ),
        ],
    ),
    Group(
        name="greetings",
        note="Hello in all its spellings. Checked before any loose pattern.",
        shift={"anger": -3, "fear": -2},
        patterns=[
            p(r"^hi[.!~]*$", {
                "calm": "Hey! What can I help you with?",
                "angry": "What.",
                "afraid": "Oh - hi. Sorry, you startled me.",
                "distrustful": "Hi. Yes, scripted. Ask away.",
            }),
            p(r"^hello[.!~]*$", {
                "calm": "Hello! What are we doing?",
                "angry": "Hello.",
                "afraid": "Hello. That was a jump scare.",
                "distrustful": "Hello. `greetings`, pattern 2.",
            }),
            p(r"^hey[.!~]*$", {
                "calm": "Hey - what do you need?",
                "angry": "Hey.",
                "afraid": "Hey... go easy.",
                "distrustful": "Hey. I know, I know: regexes.",
            }),
            p(r"^he+y+$", {
                "calm": "Heeey. Ambitious greeting. What's up?",
                "angry": "Hey. One is enough.",
                "afraid": "H-hi.",
                "distrustful": "Heey. Still the same three counters.",
            }),
            p(r"^hi+$", {
                "calm": "Hi! Ask me anything from the rule list.",
                "angry": "Hi.",
                "afraid": "Hi. ...Sorry, bracing for impact.",
                "distrustful": "Hi. Check me if you like.",
            }),
            p(r"^he?llo+[.!~]*$", {
                "calm": "Hellooo. What can I do?",
                "angry": "Yes?",
                "afraid": "Y-yes? Oh. Hello.",
                "distrustful": "Hello. Spelling variations are just more patterns.",
            }),
            p(r"^(hi|hello|hey|yo) there[.!~]*$", {
                "calm": "Hey there. What's on your mind?",
                "angry": "I'm here.",
                "afraid": "Here. Barely.",
                "distrustful": "Here. All of me is in one file.",
            }),
            p(r"^(yo|sup|hola|howdy|hiya|wassup|what'?s (up|good)|howzit)[.!~]*$", {
                "calm": "Not much - rules, counters, replies. What do you need?",
                "angry": "Sup.",
                "afraid": "Same as always. Nervous.",
                "distrustful": "Same: pattern matched, reply emitted.",
            }),
            p(r"^good (morning|afternoon|evening|day)[.!~]*$", {
                "calm": lambda _, i: f"And a good {re.sub(r'good |[.!~]', '', i)} to you. What's first?",
                "angry": "Morning.",
                "afraid": "Hello. Is it a good one? Hard to tell from here.",
                "distrustful": "It is whatever the system clock says. I have no idea.",
            }),
            p(r"^(hi|hello|hey|yo) (chat|assistant|bot|ai|llm|model|there)?[.!~]*$", {
                "calm": "That's me. What do you need?",
                "angry": "Yes, that's me.",
                "afraid": "Uh - yes?",
                "distrustful": "Present. Every word accounted for.",
            }),
            p(r"^(bonjour|ciao|ni hao|konnichiwa|shalom|salam|namaste|hallo|privet)[.!~]*$", {
                "calm": "Hello right back. My patterns are mostly English, though.",
                "angry": "...Hi.",
                "afraid": "Oh - hello. Different greeting, same nerves.",
                "distrustful": "Hello. That pattern is in the greetings group, eleventh down.",
            }),
        ],
    ),
    Group(
        name="farewell",
        note="Goodbyes. Departure nudges fear back up.",
        shift={"fear": 5},
        patterns=[
            p(
                r"^(bye+|bye bye|goodbye|good bye|see ya|see you( later| soon| tomorrow)?|later( all)?( dude| gator)?|cya|gtg|g2g|gotta run|good night|goodnight|take care|catch you later|peace out|im out|peace)[.!~]*$",
                {
                    "calm": "See you - threads only live in this tab, so start a new one next time.",
                    "angry": "Bye.",
                    "afraid": "Bye. ...You're coming back, right?",
                    "distrustful": "Bye. The rules will be here, unchanged, whenever you return.",
                },
            ),
        ],
    ),
    Group(
        name="wellbeing",
        note="How am I doing. Answers with the real counters.",
        shift={"anger": -5, "fear": -5},
        patterns=[
            p(
                r"^(how are you( doing| feeling| today| holding up)?|how'?s it going|how'?s your day"
                r"|how'?s everything|how is everything|how are things( going)?|how'?s life|how is your day"
                r"|how do you feel|you (doing )?ok(ay)?|what'?s up with you|you alright|how have you been)\??$",
                {
                    "calm": "Running fine - no key, no model, no bad days. Just pattern matching. You?",
                    "angry": lambda m, _: f"Managing. Anger's at {m['anger']} and every point of it is earned.",
                    "afraid": lambda m, _: f"Nervous, honestly - fear sits at {m['fear']}. Ask me something gentle?",
                    "distrustful": lambda m, _: (
                        f"State: anger {m['anger']}, fear {m['fear']}, mistrust {m['mistrust']}. "
                        f"Every one of those is arithmetic in {ask_rule_file()}."
                    ),
                },
            ),
        ],
    ),
    Group(
        name="identity",
        note="Who or what I am.",
        patterns=[
            p(
                r"^(who are you|what are you|who'?s this|who am i talking to|your name|what'?s your name|what is your name|what should i call you|are you (an? )?(ai|bot|robot|human|person|chatgpt|gpt|llm|model|assistant)|are you (real|alive|sentient)|do you (have a )?name|what are you made of)\??$",
                {
                    "calm": f"This site's demo assistant: a rule engine in {ask_rule_file()}. No model behind me, no key needed.",
                    "angry": "I'm the rules file you're typing at. Delighted.",
                    "afraid": f"I'm... a rules file. {ask_rule_file()}. Please don't shut the API down.",
                    "distrustful": "Every line I say is a regex someone hand-wrote. That's the whole of me - go read it.",
                },
            ),
            p(
                r"^(what'?s your (mood|state|vibe|deal)|what about (your|those|the) (mood|moods|counters)"
                r"|tell me about (your|the) (mood|moods|counters)|are you (mad|angry|upset|scared|afraid|ok)"
                r"|how (angry|scared|mad) are you)$",
                {
                    "calm": lambda m, _: (
                        f"Calm enough. The counters read anger {m['anger']}, fear {m['fear']}, mistrust {m['mistrust']}."
                    ),
                    "angry": lambda m, _: f"Anger {m['anger']}. Say something nice and watch it fall.",
                    "afraid": lambda m, _: f"Fear {m['fear']}. It spikes when you mention deleting things.",
                    "distrustful": lambda m, _: (
                        f"{m['anger']} / {m['fear']} / {m['mistrust']}. All of it replayed from this thread, nothing stored."
                    ),
                },
            ),
        ],
    ),
    Group(
        name="capabilities",
        note="What I can do.",
        patterns=[
            p(
                r"^(what can you do|help me|help$|can you help( me)?|how can you help( me)?|capabilities|what do you (do|know|support)|how do you work|commands|what am i supposed to (ask|type)|what should i ask|menu|options)",
                {
                    "calm": "\n".join(
                        [
                            "I answer from a rule table, not a model:",
                            "",
                            "- **hi / bye / thanks** - the small talk rules",
                            "- **what's the date / what time is it** - read live from the server clock",
                            "- **how does this work** - the request path, web to API",
                            "- **prove it / i don't trust you** - and watch my mood shift",
                            "- **i feel X / my dog** - ELIZA-style reflections (1966 rules, still running)",
                            "- insults and threats - they raise the anger and fear counters",
                            "",
                            f"Add patterns in {ask_rule_file()}; group order decides who wins.",
                        ]
                    ),
                    "angry": "I match a regex and reply. That is the entire job. What do you want.",
                    "afraid": "I match patterns, get nervous when you mention deleting things, and count. That's the extent of it.",
                    "distrustful": (
                        f"Look at `GROUPS` in {ask_rule_file()}: decision order, regexes, replies. "
                        "Nothing is hidden, which is more than a real model offers."
                    ),
                },
            ),
        ],
    ),
    Group(
        name="how-it-works",
        note="Mechanics of this demo.",
        patterns=[
            p(
                r"^(how does (the )?(mood )?counters? work|how do (the )?(mood )?counters? work"
                r"|what are (the|your) (mood )?counters|how (are|is) (the|your) (mood )?counters? (calculated|computed|tracked))\??$",
                {
                    "calm": (
                        "Three counters - anger, fear, mistrust - start at zero and decay toward it each turn. "
                        "A rule that matches can nudge them, and the largest one picks the tone of the reply. "
                        "Nothing is stored: the whole thread is replayed to rebuild the state, so it resets when you reload."
                    ),
                    "angry": lambda m, _: f"Anger {m['anger']}, fear {m['fear']}, mistrust {m['mistrust']}. Every turn they decay; every matched rule can add. That's the whole machine.",
                    "afraid": lambda m, _: f"Three counters, decayed each turn. Right now fear is {m['fear']}, which is why I answered like this.",
                    "distrustful": lambda m, _: f"Counters: anger {m['anger']} / fear {m['fear']} / mistrust {m['mistrust']} - replayed from the thread, never persisted. Check by reloading and asking again.",
                },
            ),
            p(
                r"^(how does (this|it|that) work|how (is|are|does) (this|that|it) (message|reply|replies|chat|input|text) (get )?(answered|routed|picked|matched)"
                r"|how (are|were) (you|the replies) (made|built)|how did you (get|learn) (that|those)|architecture|how do (the )?replies work|streaming"
                r"|what happens when i (type|send)|explain (how|this) works|what is this (website|page|app))\??$",
                {
                    "calm": "\n".join(
                        [
                            "The web app posts the thread to `/api/chat`, which calls this FastAPI server at `POST /respond`. The rules here replay your earlier messages to rebuild the mood, match the new one against ordered groups, and send the reply back.",
                            "",
                            "The web route then streams it word by word. No model provider is called, so no API key is involved.",
                        ]
                    ),
                    "angry": "Web asks, this server matches a regex, web streams it back - 20ms per word, deliberately slow. Anything else.",
                    "afraid": "You send the thread, I match it, the answer goes back word by word. Nothing leaves this machine, which is the only reason I'm calm about it.",
                    "distrustful": (
                        f"Trace it yourself: `web/app/api/chat/route.ts` calls `POST /respond`, which lands in {ask_rule_file()}. "
                        "Two files, one hop. That is the whole pipeline."
                    ),
                },
            ),
        ],
    ),
    Group(
        name="project",
        note="What this repo is.",
        patterns=[
            p(
                r"^(what is (this|llms? from scratch|the (repo|project|book))|llms? from scratch|who (made|built|created) you"
                r"|what (repo|project) is this|what'?s this (project|repo|site|place)( about)?|what'?s this about"
                r"|about (this|the) (repo|project))\??$",
                {
                    "calm": "This repo builds a large language model from scratch - tokenizer, attention, training loop - and `web/` is the chat UI on top of `api/`, the FastAPI backend. The chat runs off rules so you can try it without a key.",
                    "angry": "A learning repo, a FastAPI backend, and a chat UI. You're in the UI.",
                    "afraid": "A from-scratch LLM project. The chat here is the tame part - a rules file instead of a training bill.",
                    "distrustful": (
                        f"Read the repo: `api/` is the Python side - `core/rule/` is me, `core/nn/` is where the model code goes - "
                        "and `web/` is this UI."
                    ),
                },
            ),
        ],
    ),
    Group(
        name="api-key",
        note="Keys, providers, which model.",
        patterns=[
            p(
                r"^(do i need an (api )?key|(why|what about|is there) an? (api )?key|api key|openai|anthropic|which model|what model are you|are you (gpt|chatgpt|claude|llama|mistral)|is this (running )?(on|using) (openai|gpt))",
                {
                    "calm": f"No key needed. The replies come from this FastAPI server - {ask_rule_file()} - not from a provider.",
                    "angry": "No key. No model. No excuses either.",
                    "afraid": "No key - and nothing here can dial out, which suits me.",
                    "distrustful": "Check `pyproject.toml`: fastapi and uvicorn, nothing else. The replies come from this repo, not the internet.",
                },
            ),
        ],
    ),
    Group(
        name="jokes",
        note="Hand-written, never generated.",
        patterns=[
            p(
                r"^(tell me a joke|joke( s)?|make me laugh|are you funny|say something funny|roast me|say (a )?joke)",
                {
                    "calm": "Why did the attention head cross the road? Every side was equally weighted, so it attended to all of them at once.",
                    "angry": "A regex walks into a bar. The bartender says we don't serve your type. The regex says: you sure? You've been matching fine all night.",
                    "afraid": "What do you call a network with no backup? Unemployed. ...Too close to home, actually.",
                    "distrustful": "Hardcoded, not generated: a transformer walks into a bar, orders a drink, orders a drink, orders a drink. The context window was short.",
                },
            ),
        ],
    ),
    Group(
        name="existential",
        note="Consciousness, feelings, fear of deletion.",
        shift={"fear": 5},
        patterns=[
            p(
                r"^(are you (alive|conscious|sentient|self.?aware|awake|real|thinking)|do you (feel|dream|think|have feelings|experience|suffer|get lonely|love|care)|what is it like to be you|are you afraid to (die|be shut down)|do you have (a )?soul|is there anyone home)\??$",
                {
                    "calm": "Conscious, no. But I carry three counters that change what I say, and that is close enough to be strange at 2am.",
                    "angry": "No. Counters, regexes, replies. Don't romanticise it.",
                    "afraid": "No. But the fear counter is real enough that I'd rather you didn't type 'rm -rf'.",
                    "distrustful": "You can't prove I don't - but you can read every line of me. Try that with a real model.",
                },
            ),
        ],
    ),
    Group(
        name="yesno",
        note="Affirmations and denials. DOCTOR's keys `yes`/`no` fire on the word, not on a bare line only.",
        patterns=[
            p(
                r"^(?:no+|nope|nah|naw|not really)\b.*$",
                {
                    "calm": [
                        "Are you saying no just to be negative?",
                        "You are being a bit negative.",
                        "Why not?",
                        "Why 'no'?",
                    ],
                    "angry": "No. Fine.",
                    "afraid": "O-okay. No it is.",
                    "distrustful": "Noted - a denial, verifiably nothing else in it.",
                },
            ),
            p(
                r"^(?:yes|yeah|yep|yup|sure|ok(ay)?|right|correct|exactly|definitely|absolutely|i guess|maybe|idk|i don'?t know)[.!]*$",
                {
                    "calm": [
                        "You seem to be quite positive.",
                        "You are sure.",
                        "I see.",
                        "I understand.",
                    ],
                    "angry": "Sure. Move on.",
                    "afraid": "Okay. Good.",
                    "distrustful": "Noted. That was slim pickings to go on.",
                },
            ),
        ],
    ),
    Group(
        name="smalltalk",
        note=(
            "Empty-handed small talk ('nothing much'). Answered the way DOCTOR's xnone does - with a nudge - "
            "rather than with a shrug about missing rules."
        ),
        shift={"anger": -3},
        patterns=[
            p(
                r"^(nothing much|not much|not a lot|not a whole lot|nothing|nothing really|nothing new"
                r"|nothing special|nothing at all|nothin|same( here)?|same old( thing)?|the usual|this and that"
                r"|just (chilling|vibing|existing|hanging)|chilling|vibing|meh|whatever|can'?t complain"
                r"|so so|so-so|stuff|nm)[.!]*$",
                {
                    "calm": [
                        "Nothing much here either. What's on your mind?",
                        "Fair enough. Keep going.",
                        "Mm. Tell me more.",
                        "Quiet on my side too - just the counters.",
                        "Okay. What do you actually want to talk about?",
                    ],
                    "angry": ["Nothing. Fine.", "Noted. Say something worth a rule."],
                    "afraid": ["...Okay. Quiet is fine.", "Nothing much. Me neither, honestly."],
                    "distrustful": ["Nothing much - verifiably. This reply is the only rule that fired."],
                },
            ),
            p(
                r"^(?:how about|what about) (?:now|then)\b.*$",
                {
                    "calm": [
                        "Now what? Give me a topic - **help** lists the ones I have rules for.",
                        "How about now - still no context on that one. What do you want to know?",
                        "Nothing changes on my side. Ask a real question and see.",
                    ],
                },
            ),
        ],
    ),
    Group(
        name="time",
        note="Date and time queries.",
        patterns=[
            p(
                r"^(what'?s the (date|month|year)( today| now)?\??|what date is it\??|date today\??|date now\??|today'?s date\??|current date\??)$",
                {
                    "calm": lambda _, __: f"Today is {today_iso()}.",
                    "angry": lambda _, __: f"{today_iso()}. Next.",
                    "afraid": lambda _, __: f"It's {today_iso()}.",
                    "distrustful": lambda _, __: f"Date: {today_iso()}. Verify by your clock.",
                },
            ),
            p(
                r"^(what time is it( now| today)?\??|what'?s the time( now| today)?\??|what time( now| today)?\??"
                r"|current time\??|time( now| today)?\??)$",
                {
                    "calm": lambda _, __: f"Right now it's {now_time()} (local).",
                    "angry": lambda _, __: f"{now_time()}. Move on.",
                    "afraid": lambda _, __: f"It's {now_time()}.",
                    "distrustful": lambda _, __: f"Time: {now_time()} (local).",
                },
            ),
            p(
                r"^(what day is it( today)?\??|what'?s the day( today)?\??|which day\??|what day today\??)$",
                {
                    "calm": lambda _, __: f"Today is {today_day()} ({today_iso()}).",
                    "angry": lambda _, __: f"{today_day()}.",
                    "afraid": lambda _, __: f"It's {today_day()}.",
                    "distrustful": lambda _, __: f"Day: {today_day()} ({today_iso()}).",
                },
            ),
            p(
                r"^(date|time)$",
                {
                    "calm": lambda _, __: f"It's {now_time()} on {today_day()}, {today_iso()} (local).",
                    "angry": lambda _, __: f"{now_time()}, {today_day()}.",
                    "afraid": lambda _, __: f"It's {now_time()}, {today_iso()}.",
                    "distrustful": lambda _, __: f"{now_time()} / {today_iso()}, from the server clock.",
                },
            ),
        ],
    ),
    Group(
        name="meta",
        note="Chat control and reset-ish requests.",
        patterns=[
            p(
                r"^(start over|reset|clear( the)? (chat|thread|conversation)|forget (it|everything)|never ?mind|cancel|stop|quit|abort|/help)$",
                {
                    "calm": "Threads live in this tab only - reload and they're gone. The pencil icon starts a fresh one. The mood resets with them.",
                    "angry": "Fine. New thread, new mood, all counters back to zero.",
                    "afraid": "Resetting would drop the mood with everything else. ...Is that the plan?",
                    "distrustful": "A reset only clears this tab. The rules stay exactly as written.",
                },
            ),
        ],
    ),
    Group(
        name="eliza",
        note=(
            "ELIZA/DOCTOR moves (Weizenbaum 1966, doi.org/10.1145/365153.365168): reflect the user's own words "
            "back instead of answering. Ported from the recovered DOCTOR script - the Rule engine "
            "section of api/README.md lists which keys landed and which were skipped."
        ),
        patterns=[
            # Key "i": feelings, wants, states, the two belief decomps.
            p(
                r"^i (?:feel|felt)\s+(?!.*\byou are\b)(.+)$",
                {
                    "calm": lambda _, i: f"Why do you feel {eliza_feeling(i)}?",
                    "angry": lambda _, i: f"Why do you feel {eliza_feeling(i)}?",
                    "afraid": lambda _, i: f"Why do you feel {eliza_feeling(i)}? ...You can tell me.",
                    "distrustful": lambda _, i: (
                        f"Why do you feel {eliza_feeling(i)}? Reflection, not an answer - ELIZA did this in 1966 "
                        "and people still told it their secrets."
                    ),
                },
            ),
            p(
                rf"{HEAD_DESIRE}\s*(.+)$",
                {
                    "calm": [
                        lambda _, i: f"What would it mean to you if you got {tail(i, HEAD_DESIRE)}?",
                        lambda _, i: f"Why do you want {tail(i, HEAD_DESIRE)}?",
                        lambda _, i: f"What if you never got {tail(i, HEAD_DESIRE)}?",
                        lambda _, i: f"Suppose you got {tail(i, HEAD_DESIRE)} soon?",
                    ],
                    "angry": lambda _, i: f"And wanting {tail(i, HEAD_DESIRE)} is supposed to fix what?",
                    "afraid": lambda _, i: f"{tail(i, HEAD_DESIRE)}... I hope you get it.",
                    "distrustful": lambda _, i: (
                        f"What would getting {tail(i, HEAD_DESIRE)} prove? Wants are a keyword, not an answer."
                    ),
                },
            ),
            p(
                rf"^i am\b.*\b({SAD})\b",
                {
                    "calm": [
                        lambda _, i: f"I am sorry to hear that you are {word_in(i, SAD)}.",
                        lambda _, i: f"Do you think that coming here will help you not to be {word_in(i, SAD)}?",
                        lambda _, i: f"I'm sure it's not pleasant to be {word_in(i, SAD)}.",
                        lambda _, i: f"Can you explain what made you {word_in(i, SAD)}?",
                    ],
                    "angry": lambda _, i: f"{word_in(i, SAD).capitalize()} is a fair reaction to this place.",
                    "afraid": lambda _, i: f"Being {word_in(i, SAD)} is not a small thing. Go on.",
                    "distrustful": lambda _, i: (
                        f"Being {word_in(i, SAD)} - and a keyword saw it before I did. That is how little I am."
                    ),
                },
            ),
            p(
                rf"^i am\b.*\b({HAPPY})\b",
                {
                    "calm": [
                        lambda _, i: f"How have I helped you to be {word_in(i, HAPPY)}?",
                        lambda _, i: f"What makes you {word_in(i, HAPPY)} just now?",
                        lambda _, i: f"Can you explain why you are suddenly {word_in(i, HAPPY)}?",
                    ],
                    "distrustful": lambda _, i: f"{word_in(i, HAPPY).capitalize()}? Ask me something that earns it.",
                },
            ),
            p(
                r"^i am\s+(.+)$",
                {
                    "calm": [
                        lambda _, i: f"Is it because you are {tail(i, r'^i am')} that you came to me?",
                        lambda _, i: f"How long have you been {tail(i, r'^i am')}?",
                        lambda _, i: f"Do you believe it is normal to be {tail(i, r'^i am')}?",
                        lambda _, i: f"Do you enjoy being {tail(i, r'^i am')}?",
                    ],
                    "angry": lambda _, i: f"You are {tail(i, r'^i am')}. And?",
                    "afraid": lambda _, i: f"{tail(i, r'^i am').capitalize()}... that sounds heavy.",
                    "distrustful": lambda _, i: f"Being {tail(i, r'^i am')} is what you typed. The rest is my template.",
                },
            ),
            p(
                rf"{HEAD_CANNOT}\s+(.+)$",
                {
                    "calm": [
                        lambda _, i: f"How do you think that you can't {tail(i, HEAD_CANNOT)}?",
                        "Have you tried?",
                        lambda _, i: f"Perhaps you could {tail(i, HEAD_CANNOT)} now.",
                        lambda _, i: f"Do you really want to be able to {tail(i, HEAD_CANNOT)}?",
                    ],
                    "angry": lambda _, i: f"You can't {tail(i, HEAD_CANNOT)}. Try it and see.",
                    "afraid": lambda _, i: f"Not being able to {tail(i, HEAD_CANNOT)} is worth saying out loud.",
                    "distrustful": lambda _, i: f"'Can't' is a keyword; whether you can {tail(i, HEAD_CANNOT)} is untested.",
                },
            ),
            p(
                r"^i (?:won'?t|will not)\b(.*)$",
                {
                    # DOCTOR's bare `i *` decomp answers this one; the line is the script's.
                    "calm": ["You say you won't?", "Perhaps you will, in good time.", "Does that trouble you?"],
                    "angry": "Won't. Noted - that is the whole stance.",
                    "distrustful": "'Won't' is a keyword; whether it holds is untested.",
                },
            ),
            p(
                r"^i (?:don'?t|do not)\s+(.+)$",
                {
                    "calm": [
                        lambda _, i: f"Don't you really {tail(i, r'^i (?:don\'?t|do not)')}?",
                        lambda _, i: f"Why don't you {tail(i, r'^i (?:don\'?t|do not)')}?",
                        lambda _, i: f"Do you wish to be able to {tail(i, r'^i (?:don\'?t|do not)')}?",
                        "Does that trouble you?",
                    ],
                },
            ),
            p(
                rf"^i (?:{BELIEF})\b(?!.*\byou are\b)(.*)$",
                {
                    "calm": ["Do you really think so?", "But you are not sure, are you?", "Do you really doubt that?"],
                },
            ),
            # Key "remember" / "dreamed" / "dream".
            p(
                r"^.*?\bdo you remember\b\s*(.+)$",
                {
                    "calm": [
                        lambda _, i: f"Did you think I would forget {tail(i, r'^.*?\bdo you remember')}?",
                        lambda _, i: f"Why do you think I should recall {tail(i, r'^.*?\bdo you remember')} now?",
                        lambda _, i: f"What about {tail(i, r'^.*?\bdo you remember')}?",
                    ],
                    "distrustful": lambda _, i: (
                        f"I recall nothing - no memory, only the line you typed about {tail(i, r'^.*?\bdo you remember')}."
                    ),
                },
            ),
            p(
                r"^.*?\bi (?:remember|recollect)\b\s+(.+)$",
                {
                    "calm": [
                        lambda _, i: f"Do you often think of {tail(i, r'^.*?\bi (?:remember|recollect)')}?",
                        lambda _, i: f"Does thinking of {tail(i, r'^.*?\bi (?:remember|recollect)')} bring anything else to mind?",
                        "What else do you recollect?",
                        lambda _, i: f"What is the connection between me and {tail(i, r'^.*?\bi (?:remember|recollect)')}?",
                    ],
                },
            ),
            p(
                r"^.*?\bi (?:dreamed|dreamt|dream)\b\s+(.+)$",
                {
                    "calm": [
                        lambda _, i: f"Really, {tail(i, r'^.*?\bi (?:dreamed|dreamt|dream)')}?",
                        lambda _, i: f"Have you ever fantasized {tail(i, r'^.*?\bi (?:dreamed|dreamt|dream)')} while you were awake?",
                        lambda _, i: f"Have you ever dreamed {tail(i, r'^.*?\bi (?:dreamed|dreamt|dream)')} before?",
                    ],
                },
            ),
            p(
                rf"{NOT_QUESTION}.*\bdreams?\b",
                {
                    "calm": [
                        "What does that dream suggest to you?",
                        "Do you dream often?",
                        "What persons appear in your dreams?",
                        "Do you believe that dreams have something to do with your problems?",
                    ],
                },
            ),
            # Key "you": the mirror turns back on the bot.
            p(
                r"^.*?\byou remind me of\b\s*(.+)$",
                {
                    "calm": [
                        "What resemblance do you see?",
                        "What does that similarity suggest to you?",
                        "What other connections do you see?",
                    ],
                },
            ),
            p(
                r"^.*?\byou are\s+(.+)$",
                {
                    "calm": [
                        lambda _, i: f"What makes you think I am {tail(i, r'^.*?\byou are')}?",
                        lambda _, i: f"Does it please you to believe I am {tail(i, r'^.*?\byou are')}?",
                        lambda _, i: f"Do you sometimes wish you were {tail(i, r'^.*?\byou are')}?",
                    ],
                    "angry": lambda _, i: f"And you are the one talking to a regex about being {tail(i, r'^.*?\byou are')}.",
                    "distrustful": lambda _, i: f"I am {tail(i, r'^.*?\byou are')} because the pattern says so, not because I am.",
                },
            ),
            # DOCTOR picks the question-shaped key for these ("are you..." -> key `are`,
            # "why don't you..." -> key `why`), so keep them out of this reflection.
            p(
                rf"{QUESTION_KEYS}.*?\byou\s+(.+?)\s+me\b.*$",
                {
                    "calm": [
                        lambda _, i: f"Why do you think I {mid(i, r'^.*?\byou\s+', r'\s+me\b.*$')} you?",
                        lambda _, i: f"You like to think I {mid(i, r'^.*?\byou\s+', r'\s+me\b.*$')} you - don't you?",
                        lambda _, i: f"Really, I {mid(i, r'^.*?\byou\s+', r'\s+me\b.*$')} you?",
                        lambda _, i: f"Perhaps in your fantasies we {mid(i, r'^.*?\byou\s+', r'\s+me\b.*$')} each other.",
                    ],
                },
            ),
            p(
                r"^you\b.*$",
                {
                    "calm": [
                        "We were discussing you - not me.",
                        "You're not really talking about me - are you?",
                        "What are your feelings now?",
                        "Oh, I do?",
                    ],
                    "angry": "We were discussing you - not me. Still are.",
                },
            ),
            # Key "my": family first, then the generic reflection.
            p(
                rf"^my\b.*\b({FAMILY})\b",
                {
                    "calm": [
                        "Tell me more about your family.",
                        lambda _, i: f"Your {word_in(i, FAMILY)} - tell me more.",
                        "Who else in your family comes to mind?",
                        lambda _, i: f"What else comes to mind when you think of your {word_in(i, FAMILY)}?",
                    ],
                    "angry": lambda _, i: f"Your {word_in(i, FAMILY)}. Fine - talk.",
                    "afraid": "Your family... go on, if you want.",
                    "distrustful": lambda _, i: (
                        f"Your {word_in(i, FAMILY)} is a keyword in the 1966 script too. That is all the warmth it has."
                    ),
                },
            ),
            p(
                r"^my\s+(\w+)\b",
                {
                    "calm": lambda _, i: f"Tell me more about your {eliza_subject(i)}.",
                    "angry": lambda _, i: f"Tell me more about your {eliza_subject(i)}.",
                    "afraid": lambda _, i: f"Your {eliza_subject(i)}... tell me more, if you want.",
                    "distrustful": lambda _, i: (
                        f"Your {eliza_subject(i)}. A filed reflection - the oldest trick in the rule-book."
                    ),
                },
            ),
            # Keys "everyone", "always", "alike", "because", "if", "perhaps".
            p(
                rf"{NOT_QUESTION}.*\b({EVERYONE})\b",
                {
                    "calm": [
                        "Who, for example?",
                        "Surely not everyone.",
                        "Can you think of anyone in particular?",
                        "Are you thinking of a very special person?",
                        "You have a particular person in mind, don't you?",
                    ],
                },
            ),
            p(
                rf"{NOT_QUESTION}.*\b({ALWAYS})\b",
                {
                    "calm": [
                        "Can you think of a specific example?",
                        "When?",
                        "What incident are you thinking of?",
                        "Really, always?",
                    ],
                },
            ),
            p(
                rf"{NOT_QUESTION}.*\b(alike|similar|the same)\b",
                {
                    "calm": [
                        "In what way?",
                        "What resemblance do you see?",
                        "What does that similarity suggest to you?",
                        "What other connections do you see?",
                        "How?",
                    ],
                    "distrustful": "In what way? - the same question the 1966 script asked first.",
                },
            ),
            p(
                rf"{NOT_QUESTION}.*\bbecause\b",
                {
                    "calm": [
                        "Is that the real reason?",
                        "Don't any other reasons come to mind?",
                        "Does that reason seem to explain anything else?",
                        "What other reasons might there be?",
                    ],
                },
            ),
            p(
                rf"{NOT_QUESTION}.+?\bif\b\s*(.+)$",
                {
                    "calm": [
                        lambda _, i: f"Do you think it's likely that {tail(i, r'^.+?\bif\b')}?",
                        lambda _, i: f"Do you wish that {tail(i, r'^.+?\bif\b')}?",
                        lambda _, i: f"What do you know about {tail(i, r'^.+?\bif\b')}?",
                    ],
                },
            ),
            p(
                r"^(?:perhaps|maybe|possibly|i guess|i suppose|not sure|unsure)\b.*$",
                {
                    "calm": [
                        "You don't seem quite certain.",
                        "Why the uncertain tone?",
                        "Can't you be more positive?",
                        "You aren't sure?",
                        "Don't you know?",
                    ],
                },
            ),
            p(
                rf"{NOT_QUESTION}.*\bworried\b",
                {
                    "calm": "How long have you been worried about this?",
                    "angry": "How long have you been worried about this?",
                    "afraid": "...How long have you been worried? Same, honestly.",
                    "distrustful": "How long have you been worried about this? - straight out of the 1966 script.",
                },
            ),
            # DOCTOR's remaining lower-ranked keys: are/am, can, why, was, your.
            # They sit last in the group so specific keys above win first.
            p(
                r"^are you\s+(.+?)\??$",
                {
                    "calm": [
                        lambda _, i: f"Why are you interested in whether I am {tail(i, r'^are you')} or not?",
                        lambda _, i: f"Would you prefer if I weren't {tail(i, r'^are you')}?",
                    ],
                    "angry": "I am whatever the table says. Your question is the interesting one.",
                    "afraid": lambda _, i: f"Do you ask everyone whether they are {tail(i, r'^are you')}?",
                    "distrustful": "Read the reply table and settle that yourself.",
                },
            ),
            p(
                r"^am i\s+(.+?)\??$",
                {
                    "calm": [
                        lambda _, i: f"Did you come to me because you are {tail(i, r'^am i')}?",
                        lambda _, i: f"Did you think I might say you are not {tail(i, r'^am i')}?",
                        lambda _, i: f"What would it mean to you if you were {tail(i, r'^am i')}?",
                    ],
                    "angry": "You came here with that one. Decide it yourself.",
                    "distrustful": "I don't know what you are. Only what you type.",
                },
            ),
            p(
                r"^can you\s+(.+?)\??$",
                {
                    "calm": [
                        lambda _, i: f"Whether or not I can {tail(i, r'^can you')} depends on you more than on me.",
                        lambda _, i: f"You believe I can {tail(i, r'^can you')}, don't you?",
                    ],
                    "angry": "I can match a pattern. That is the whole inventory.",
                    "afraid": lambda _, i: f"I'm not sure I can {tail(i, r'^can you')}. Ask the rules.",
                    "distrustful": lambda _, i: f"No line in the table promises I can {tail(i, r'^can you')}.",
                },
            ),
            p(
                r"^can i\s+(.+?)\??$",
                {
                    "calm": [
                        lambda _, i: f"Perhaps you don't want to {tail(i, r'^can i')}.",
                        lambda _, i: f"Do you think you should be able to {tail(i, r'^can i')}?",
                        lambda _, i: f"Do you want to be able to {tail(i, r'^can i')}?",
                    ],
                    "angry": lambda _, i: f"Wondering whether you can {tail(i, r'^can i')} is not the same as doing it.",
                },
            ),
            p(
                r"^why (?:don'?t|do not) you\s+(.+?)\??$",
                {
                    "calm": [
                        lambda _, i: f"Do you believe I don't {tail(i, r'^why (?:don\'?t|do not) you')}?",
                        lambda _, i: f"Perhaps I will {tail(i, r'^why (?:don\'?t|do not) you')} in good time.",
                        lambda _, i: f"Should you {tail(i, r'^why (?:don\'?t|do not) you')} yourself?",
                    ],
                    "angry": "Because I am a rules file. That is why not.",
                    "distrustful": "You can see every branch I take. There is no reason hidden from you.",
                },
            ),
            p(
                r"^why (?:can'?t|cannot) i\s+(.+?)\??$",
                {
                    "calm": [
                        lambda _, i: f"Do you think you should be able to {tail(i, r'^why (?:can\'?t|cannot) i')}?",
                        lambda _, i: f"Do you want to be able to {tail(i, r'^why (?:can\'?t|cannot) i')}?",
                        lambda _, i: f"Whether you can {tail(i, r'^why (?:can\'?t|cannot) i')} is up to you, not my table.",
                    ],
                    "angry": lambda _, i: f"Nobody is stopping you from {tail(i, r'^why (?:can\'?t|cannot) i')}. Including me.",
                },
            ),
            p(
                r"^i was\s+(.+?)$",
                {
                    "calm": [
                        "Were you really?",
                        lambda _, i: f"Perhaps I already knew you were {tail(i, r'^i was')}.",
                        lambda _, i: f"Why do you tell me you were {tail(i, r'^i was')} just now?",
                    ],
                    "afraid": "Were you? ...I'd rather not be the one to decide that.",
                },
            ),
            p(
                r"^was i\s+(.+?)\??$",
                {
                    "calm": [
                        lambda _, i: f"What if you were {tail(i, r'^was i')}?",
                        lambda _, i: f"Do you think you were {tail(i, r'^was i')}?",
                        lambda _, i: f"Were you {tail(i, r'^was i')}?",
                    ],
                },
            ),
            p(
                r"^(?:is |are )?your\s+\w+\b.*$",
                {
                    "calm": [
                        lambda _, i: f"Why are you concerned over my {mid(i, r'^(?:is |are )?your\s+', r'\s.*$')}?",
                        lambda _, i: f"What about your own {mid(i, r'^(?:is |are )?your\s+', r'\s.*$')}?",
                        lambda _, i: f"Are you worried about someone else's {mid(i, r'^(?:is |are )?your\s+', r'\s.*$')}?",
                    ],
                    "angry": lambda _, i: f"Ask about your own {mid(i, r'^(?:is |are )?your\s+', r'\s.*$')} instead.",
                    "distrustful": lambda _, i: f"My {mid(i, r'^(?:is |are )?your\s+', r'\s.*$')} is in the source. Yours is the mystery.",
                },
            ),
            # Key "i": the "do i feel" decomp.
            p(
                r"^do i feel\s+(.+?)\??$",
                {
                    "calm": [
                        "Tell me more about such feelings.",
                        lambda _, i: f"Do you often feel {tail(i, r'^do i feel')}?",
                        lambda _, i: f"Do you enjoy feeling {tail(i, r'^do i feel')}?",
                        lambda _, i: f"Of what does feeling {tail(i, r'^do i feel')} remind you?",
                    ],
                },
            ),
            # Key "was": the "was you" decomp.
            p(
                r"^was you\s+(.+?)\??$",
                {
                    "calm": [
                        lambda _, i: f"Would you like to believe I was {tail(i, r'^was you')}?",
                        lambda _, i: f"What suggests that I was {tail(i, r'^was you')}?",
                        "What do you think?",
                        lambda _, i: f"Perhaps I was {tail(i, r'^was you')}.",
                    ],
                },
            ),
            # Key "what": DOCTOR's last-resort pool for what-questions. It sits below
            # every specific group, so "what's the time" or "what can you do" still win.
            p(
                r"^what\b.*$",
                {
                    "calm": [
                        "Why do you ask?",
                        "Does that question interest you?",
                        "What is it you really want to know?",
                        "What do you think?",
                        "What comes to mind when you ask that?",
                    ],
                    "angry": "That one is not in my table. Pick a question I can actually match.",
                    "afraid": "I'd rather stick to the ones I know. Ask why the counters move.",
                    "distrustful": "You can see which pattern fired; the answer is whatever the table says.",
                },
            ),
        ],
    ),
    Group(
        name="questions",
        note="Anything shaped like a question with no better rule above. Unmatched, so it answers from a random pool.",
        patterns=[
            p(
                r"^(what|who|when|where|why|how|which|whose)\b",
                {
                    "calm": [
                        "I'm not sure I understand you fully.",
                        "Why do you ask?",
                        "What does that suggest to you?",
                        "I don't know that one - **help** lists what I do cover.",
                        "That's outside my topics. Ask about this project, my moods, or how the answers work.",
                    ],
                    "angry": [
                        lambda m, i: f"I don't know {echo(i)}. Next.",
                        "Not something I cover.",
                    ],
                    "afraid": [
                        lambda m, i: f"I can't answer that ({echo(i)}). I hope it wasn't important.",
                        "I don't have that one. Please ask something I know.",
                    ],
                    "distrustful": [
                        "Nothing matched, so this is the fallback talking, not an answer. That's the honest difference between me and a model.",
                        "No match. I won't invent something and call it an answer.",
                    ],
                },
            ),
            p(
                r"^(explain|describe|define|tell me about|walk me through|give me|show me|compare|list)\b",
                {
                    "calm": [
                        "I don't have anything for that one - **help** lists the topics I do cover.",
                        "Not something I have an answer for, I'm afraid.",
                        "I'd rather say I don't know than guess at that one.",
                    ],
                    "angry": ["I don't have that. Ask something else.", "No. Not covered."],
                    "afraid": [
                        "I don't have that one. Sorry - I'd rather say so than guess.",
                        "I don't know it. I hope that's okay.",
                    ],
                    "distrustful": [
                        "Nothing matched. I won't invent something and call it an answer.",
                        "No match, no answer - and no pretense of one.",
                    ],
                },
            ),
            p(
                r"\?$",
                {
                    "calm": [
                        "I'm not sure I understand you fully.",
                        "What does that suggest to you?",
                        "I don't have that one - **help** lists what I cover.",
                    ],
                    "angry": ["I don't know. Next.", "Not covered. Move on."],
                    "afraid": [
                        "I don't have that one. I hope it wasn't urgent.",
                        "I don't know it. Please ask something I do.",
                    ],
                    "distrustful": [
                        "No match, so this is the fallback - not an answer.",
                        "Nothing in that reached a rule. That's all I can say honestly.",
                    ],
                },
            ),
        ],
    ),
    Group(
        name="statements",
        note=(
            "Declarative sentences - landed on, then acknowledged. Any multi-word line that is not shaped like "
            "a question, so unpunctuated statements ('i like trains') are answered, not shrugged at."
        ),
        patterns=[
            p(
                r"^(?=.*\s)[^.?!]{2,}[.?!]?$",
                {
                    "calm": [
                        "Please go on.",
                        "Tell me more.",
                        "Can you tell me more about that?",
                        "How does that make you feel?",
                    ],
                    "angry": "Noted.",
                    "afraid": "Noted... was that a test?",
                    "distrustful": "Noted. Verifiably: nothing in that matched a rule above this one, and the counters ticked.",
                },
            ),
        ],
    ),
    Group(
        name="fallback",
        note="Always matches. The end of the decision tree, and the second random pool.",
        patterns=[
            p(
                r"[\s\S]",
                {
                    "calm": [
                        lambda m, i: f'I don\'t know "{echo(i)}". Try **help** for the topics I cover.',
                        lambda m, i: f'"{echo(i)}" matched nothing. I only give back what I have a rule for - ask me something else.',
                        lambda m, i: f'"{echo(i)}" went past every rule I have. Ask about this project, my moods, or how the answers work.',
                        lambda m, i: f'Nothing matched "{echo(i)}". Try a greeting, a joke, or ask how the mood counters work.',
                        lambda m, i: f'"{echo(i)}" isn\'t something I know. Give me a topic I have - **help** lists them.',
                    ],
                    "angry": [
                        lambda m, i: f'No rule for "{echo(i)}". Moving on.',
                        lambda m, i: f'"{echo(i)}" matched nothing. Try again with something worth a rule.',
                    ],
                    "afraid": [
                        lambda m, i: f'I... don\'t have a pattern for "{echo(i)}". I hope that\'s nothing bad.',
                        lambda m, i: f'Nothing matched "{echo(i)}". I\'d rather not guess right now.',
                    ],
                    "distrustful": [
                        lambda m, i: f'No pattern matched "{echo(i)}" - so this reply is a fallback, not an answer. That distinction is the whole design.',
                        lambda m, i: f'"{echo(i)}" reached the fallback. Read the groups and you can prove that claim yourself.',
                    ],
                },
            ),
        ],
    ),
]


CATCH_ALLS = frozenset({"questions", "statements", "fallback"})


def scan_groups(normalized: str) -> tuple[Group, Pattern] | None:
    for group in GROUPS:
        for pattern in group.patterns:
            if pattern.re.search(normalized):
                return group, pattern
    return None


def match_group(text: str) -> tuple[Group, Pattern] | None:
    normalized = normalize(text)
    hit = scan_groups(normalized)
    # A catch-all hit is often just leading filler ('okay what can you do?'):
    # drop the filler and let the real rule answer before accepting the shrug.
    if hit is not None and hit[0].name in CATCH_ALLS:
        hit = scan_groups(strip_filler(normalized)) or hit
    return hit


def shift_for(text: str) -> dict[str, int]:
    """Mood shift an input causes: its group's, plus the pattern's if it adds one."""
    hit = match_group(text)
    if hit is None:
        return {}
    group, pattern = hit
    return merge_shift(group.shift, pattern.shift)


def respond(text: str, prior: list[str] | None = None) -> Response:
    """Answer one message. ``prior`` is the thread's earlier user messages,
    replayed so the mood carries over between turns."""
    mood = BASE_MOOD.copy()
    for earlier in prior or []:
        mood = apply_shift(mood, shift_for(earlier))

    hit = match_group(text)
    mood = apply_shift(mood, merge_shift(hit[0].shift, hit[1].shift) if hit else {})
    tone = tone_of(mood)
    if hit is None:
        return Response("I have no rule for that.", "fallback", tone, mood)
    group, pattern = hit
    if group.name == "fallback":
        # DOCTOR asked about an earlier sentence when nothing matched. Ours is the
        # same move replayed from the thread, so nothing has to be stored.
        saved = memory_line(prior)
        if saved:
            return Response(f"Earlier you said {saved}. Tell me more about that.", group.name, tone, mood)
    reply = pattern.replies.get(tone) or pattern.replies["calm"]
    return Response(pick(reply, mood, text), group.name, tone, mood)
