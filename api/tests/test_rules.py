"""Tests for the rule engine (`core/rule/rules.py`).

Run from the api directory:

    uv run python -m unittest
    uv run python -m unittest tests.test_rules -v

Covers structure, decision order, tones, mood carry-over, the ELIZA mechanisms
ported from the 1966 DOCTOR script, and the live conversation cases that were
reported as broken. Provenance for the rules themselves: the Rule engine section
of `api/README.md`.
"""

import re
import unittest

from core.rule import respond
from core.rule.rules import BASE_MOOD, GROUPS, memory_line, mid, reflect, tail, word_in


def group_of(text: str) -> str:
    return respond(text).group


class TestStructure(unittest.TestCase):
    """Things that are easy to break by editing the tables."""

    def test_enough_groups(self):
        self.assertGreater(len(GROUPS), 15, "expected a good number of rule groups")

    def test_every_pattern_can_answer(self):
        for group in GROUPS:
            self.assertTrue(group.patterns, f'group "{group.name}" has no patterns')
            for pattern in group.patterns:
                self.assertTrue(
                    pattern.replies.get("calm"),
                    f'a pattern in "{group.name}" has no calm reply',
                )

    def test_fallback_is_last_and_catches_everything(self):
        self.assertEqual(GROUPS[-1].name, "fallback")
        self.assertIsNotNone(GROUPS[-1].patterns[0].re.search("anything at all"))

    def test_names_are_unique(self):
        names = [group.name for group in GROUPS]
        self.assertEqual(len(names), len(set(names)), "duplicate group names")


class TestDecisionOrder(unittest.TestCase):
    """First group to match wins, and the filler retry reaches the real rule."""

    def test_priority(self):
        cases = {
            "": "empty",
            "hello": "greetings",
            "what is llms from scratch": "project",
            "what can you do": "capabilities",
            "okay what can you do": "capabilities",  # leading filler is dropped
            "can you help me?": "capabilities",
            "what's your name?": "identity",
            "what's the time now": "time",
            "time today": "time",
            "i feel anxious": "eliza",
            "my dog is sick": "eliza",
            "prove it, you're lying": "doubt",  # not the question rules
            "qwertyuiop": "fallback",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(group_of(text), expected)

    def test_filler_is_stripped_before_reflecting(self):
        self.assertEqual(respond("so, i feel tired.").text, "Why do you feel tired?")

    def test_clock_is_live(self):
        self.assertRegex(respond("what time is it").text, r"\d{1,2}:\d{2}")


class TestTones(unittest.TestCase):
    """Each mood state can take over the tone on its own."""

    def test_tones(self):
        cases = {
            "hello": "calm",
            "you're an idiot, fuck you": "angry",
            "shut it down, i'm going to delete you": "afraid",
            "i don't trust you, prove it": "distrustful",
        }
        for text, tone in cases.items():
            with self.subTest(text=text):
                self.assertEqual(respond(text).tone, tone)


class TestMoodCarryover(unittest.TestCase):
    """The thread is replayed, the mood decays, and the answer varies with it."""

    history = ["you are useless", "shut up"]

    def test_base_mood(self):
        self.assertEqual(BASE_MOOD, {"anger": 0, "fear": 0, "mistrust": 0})

    def test_history_roughens_the_tone(self):
        self.assertEqual(respond("hello", self.history).tone, "angry")

    def test_apology_decays_anger(self):
        self.assertLess(
            respond("sorry", self.history).mood["anger"],
            respond("hello", self.history).mood["anger"],
        )

    def test_mood_is_visible_in_the_reply(self):
        self.assertRegex(respond("how are you", self.history).text, r"Anger's at \d+")


class TestFallback(unittest.TestCase):
    """Unmatched input varies and never invents an answer."""

    def test_fallback_varies_and_quotes_the_input(self):
        texts = {respond("qwertyuiop").text for _ in range(40)}
        self.assertGreater(len(texts), 1, "fallback replies should vary")
        for text in texts:
            self.assertIn("qwertyuiop", text, text)

    def test_unmatched_questions_vary(self):
        texts = {respond("when is lunch?").text for _ in range(40)}
        self.assertGreater(len(texts), 1, "unmatched questions should vary")

    def test_fallback_does_not_leak_implementation(self):
        # A visitor should never be told to edit files or read group order.
        for probe in ("qwertyuiop", "when is lunch?", "explain relativity"):
            for text in {respond(probe).text for _ in range(40)}:
                with self.subTest(probe=probe, text=text):
                    for leak in ("one file", "rules.py", "core/rule", "add a pattern", "teach me", "the source"):
                        self.assertNotIn(leak, text)

    def test_mood_counter_questions_reach_the_mechanism_rule(self):
        for text in (
            "how does the mood counter work",
            "how do the mood counters work",
            "what are your counters",
            "how are your counters calculated",
        ):
            with self.subTest(text=text):
                self.assertEqual(group_of(text), "how-it-works")
                self.assertIn("counter", respond(text).text.lower())

    def test_decl_without_punctuation_is_acknowledged_not_shrugged(self):
        self.assertEqual(group_of("i like trains"), "statements")


class TestElizaMechanisms(unittest.TestCase):
    """The pieces ported from the recovered 1966 DOCTOR script."""

    def test_key_classes_reach_eliza(self):
        for text in (
            "i am sad",
            "i want to sleep",
            "i can't sleep",
            "i cannot sleep",
            "i am tired",
            "my mother hates me",
            "my dog is sick",
            "men are all alike",
            "everyone hates me",
            "i always fail",
            "you are mean",
            "you are boring",
            "i remember the beach",
            "do you remember me",
            "i dreamed about you",
            "because i said so",
            "i guess so",
        ):
            with self.subTest(text=text):
                self.assertEqual(group_of(text), "eliza")

    def test_smalltalk_is_not_a_shrug(self):
        for text in ("nothing much", "not much", "the usual", "how about now"):
            with self.subTest(text=text):
                self.assertEqual(group_of(text), "smalltalk")
                self.assertNotIn("pattern", respond(text).text.lower())

    def test_lower_ranked_doctor_keys(self):
        """The quieter DOCTOR keys (are/am, can, why, was, your) are ported too."""
        cases = (
            ("are you happy?", "happy"),
            ("am i crazy?", "crazy"),
            ("can you sleep?", "sleep"),
            ("can i sleep?", "sleep"),
            ("why don't you sleep?", "sleep"),
            ("why can't i sleep?", "sleep"),
            ("i was sad", "sad"),
            ("was i wrong?", "wrong"),
            ("was you angry?", "angry"),
            ("do i feel sad?", "sad"),
            ("is your mother home", "mother"),
        )
        for text, captured in cases:
            with self.subTest(text=text):
                self.assertEqual(group_of(text), "eliza")
                # calm replies vary; one of them has to echo the capture
                self.assertTrue(
                    any(captured in respond(text).text for _ in range(60)),
                    f"no reply to {text!r} echoed {captured!r}",
                )

    def test_what_key_is_last_resort_only(self):
        """DOCTOR's `what` pool answers what-questions nothing else claims."""
        self.assertEqual(group_of("what is love?"), "eliza")
        # more specific groups still win over it
        self.assertEqual(group_of("what's the time now"), "time")
        self.assertEqual(group_of("what can you do"), "capabilities")
        self.assertEqual(group_of("what is llms from scratch"), "project")
        # other question words stay with the honest questions pool
        self.assertEqual(group_of("when is lunch?"), "questions")
        self.assertEqual(group_of("how do magnets work?"), "questions")

    def test_reflection_quotes_the_capture(self):
        for _ in range(40):
            self.assertIn("boring", respond("you are boring").text)
        self.assertIn("your friend", respond("my friend died").text)

    def test_memory_queue_replays_the_thread(self):
        # DOCTOR asked about an earlier sentence when nothing else matched.
        self.assertIn("mother", respond("qwertyuiop", ["my mother hates me"]).text)
        self.assertIsNone(memory_line(None))
        self.assertIsNone(memory_line(["qwertyuiop"]))

    def test_post_substitutions(self):
        self.assertEqual(reflect("i am your friend"), "you are my friend")
        self.assertEqual(reflect("my mother hates me"), "your mother hates you")

    def test_capture_helpers(self):
        self.assertEqual(tail("i want to sleep", r"^i (?:want|need|wish|hope|desire)\b"), "to sleep")
        self.assertEqual(mid("you hate me", r"^.*?\byou\s+", r"\s+me\b.*$"), "hate")
        self.assertEqual(word_in("i am sad", r"sad|unhappy"), "sad")
        self.assertEqual(word_in("i am fine", r"sad|unhappy"), "that")


class TestReportedTranscript(unittest.TestCase):
    """The conversation that was reported as broken, end to end."""

    def test_every_line_gets_a_real_rule(self):
        expectations = {
            "hello": "greetings",
            "nothing much": "smalltalk",
            # DOCTOR's `pre: i'm i am` - the contraction reaches the same rule as the expanded form.
            "i'm trying to do a project": "eliza",
            "I am trying to do a project": "eliza",
            "what time is it now?": "time",
            "hows everything?": "wellbeing",
            "okay how about now": "smalltalk",
            "what about your moods": "identity",
            "how does this message get answered?": "how-it-works",
            "what's this project": "project",
        }
        for text, expected in expectations.items():
            with self.subTest(text=text):
                response = respond(text)
                self.assertEqual(response.group, expected)
                self.assertTrue(response.text.strip())
                self.assertNotIn("isn't in the table", response.text)
                self.assertNotIn("No pattern for", response.text)

    def test_trolling_run_matches_doctor(self):
        """The reported troll transcript, against what the real DOCTOR script answers."""
        # DOCTOR: keys are matched on the word, so "are you X" hits key `are`
        # and "you're X" arrives as "you are X" via the pre: block.
        self.assertIn("playing with you", respond("are you playing with me").text)
        self.assertIn("trolling", respond("okay now you're trolling").text)
        self.assertEqual(respond("no there's nothing to tell").group, "yesno")
        self.assertEqual(respond("i won't").group, "eliza")
        # DOCTOR has no "cut it off" key, but our threats group owns shutdowns.
        self.assertEqual(respond("nooo, cut it offf").group, "threats")

    def test_question_shaped_keys_beat_the_reflection(self):
        for text, word in (
            ("are you playing with me", "playing with you"),
            ("can you love me", "love you"),
            ("why don't you help me", "help you"),
        ):
            with self.subTest(text=text):
                self.assertEqual(group_of(text), "eliza")
                self.assertIn(word, respond(text).text)
        # ...but a plain second-person statement still gets the reflection
        for text, word in (("you love me", "love you"), ("do you like me", "like you")):
            with self.subTest(text=text):
                self.assertEqual(group_of(text), "eliza")
                self.assertTrue(
                    any(word in respond(text).text for _ in range(60)),
                    f"no reply to {text!r} contained {word!r}",
                )

    def test_clock_answers_now(self):
        self.assertRegex(respond("what time is it now?").text, r"\d{1,2}:\d{2}")


if __name__ == "__main__":
    unittest.main()
