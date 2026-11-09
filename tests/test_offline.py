"""Offline tests: no API keys, no network, no Alexa account.

    pip install -r lambda/requirements.txt
    python -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lambda"))
os.environ["LLM_API_KEY"] = ""  # make sure no real client is created
import lambda_function as lf  # noqa: E402


def envelope(intent, value, slot="query", history=None):
    return {
        "version": "1.0",
        "session": {"new": False, "sessionId": "s", "application": {"applicationId": "a"},
                    "attributes": {"history": history or []}, "user": {"userId": "u"}},
        "context": {"System": {"application": {"applicationId": "a"}, "user": {"userId": "u"},
                               "device": {"deviceId": "d", "supportedInterfaces": {}},
                               "apiEndpoint": "https://api.amazonalexa.com", "apiAccessToken": "x"}},
        "request": {"type": "IntentRequest", "requestId": "r", "locale": "en-US",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "intent": {"name": intent, "confirmationStatus": "NONE",
                               "slots": {slot: {"name": slot, "value": value,
                                                "confirmationStatus": "NONE"}}}},
    }


class FakeModel:
    """Stands in for _ask_llm and _web_search and records what they received."""

    def __init__(self, ok=True, answer="Fine answer."):
        self.ok, self.answer, self.calls, self.searches = ok, answer, [], []

    def ask(self, history, context=None, timeout=0):
        self.calls.append({"history": history, "context": context, "timeout": timeout})
        return self.ok, self.answer

    def search(self, query, timeout):
        self.searches.append(query)
        return "[1] Example - example.com: some current fact"


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeModel()
        self._orig = (lf._ask_llm, lf._web_search, lf.SEARCH_API_KEY)
        lf._ask_llm, lf._web_search = self.fake.ask, self.fake.search
        lf.SEARCH_API_KEY = ""

    def tearDown(self):
        lf._ask_llm, lf._web_search, lf.SEARCH_API_KEY = self._orig

    def speak(self, out):
        return out["response"]["outputSpeech"]["ssml"]

    def test_question_word_is_put_back(self):
        lf.lambda_handler(envelope("QuestionWhoIntent", "invented the radio"), None)
        self.assertEqual(self.fake.calls[-1]["history"][-1]["content"], "who invented the radio")

    def test_catch_all_keeps_whole_sentence(self):
        lf.lambda_handler(envelope("FreeTalkIntent", "my plant has yellow leaves", slot="phrase"), None)
        self.assertEqual(self.fake.calls[-1]["history"][-1]["content"], "my plant has yellow leaves")

    def test_history_kept_only_on_success(self):
        out = lf.lambda_handler(envelope("QueryIntent", "about volcanoes"), None)
        self.assertEqual(len(out["sessionAttributes"]["history"]), 2)
        self.fake.ok, self.fake.answer = False, "The model took too long to answer."
        out = lf.lambda_handler(envelope("QueryIntent", "about lava"), None)
        self.assertEqual(out["sessionAttributes"]["history"], [])
        self.assertIn("took too long", self.speak(out))

    def test_session_stays_open(self):
        out = lf.lambda_handler(envelope("QueryIntent", "about volcanoes"), None)
        self.assertFalse(out["response"].get("shouldEndSession", False))

    def test_search_forced_by_search_intent(self):
        lf.SEARCH_API_KEY = "test"
        lf.lambda_handler(envelope("SearchIntent", "tallest building in the world"), None)
        self.assertEqual(self.fake.searches, ["tallest building in the world"])
        self.assertIn("Web search results", self.fake.calls[-1]["context"])

    def test_no_search_for_venting(self):
        lf.SEARCH_API_KEY = "test"
        lf.lambda_handler(envelope("FreeTalkIntent", "today was a rough day at work", slot="phrase"), None)
        self.assertEqual(self.fake.searches, [])

    def test_no_key_current_question_gets_warning_context(self):
        lf.lambda_handler(envelope("QuestionWhatIntent", "is the bitcoin price today"), None)
        self.assertEqual(self.fake.calls[-1]["context"], lf.NO_SEARCH_CONTEXT)

    def test_time_budget_respected(self):
        lf.lambda_handler(envelope("QueryIntent", "about volcanoes"), None)
        self.assertLessEqual(self.fake.calls[-1]["timeout"], lf.REQUEST_TIMEOUT_SECONDS)


class HelperTests(unittest.TestCase):
    def test_needs_search(self):
        for q in ["what's the bitcoin price", "who won the game last night", "latest news",
                  "weather forecast for tomorrow", "what is the current exchange rate"]:
            self.assertTrue(lf._needs_search(q), q)
        for q in ["why is the sky blue", "write a poem about coffee", "how many legs does a spider have"]:
            self.assertFalse(lf._needs_search(q), q)
        self.assertFalse(lf._needs_search("today was a rough day", is_question=False))

    def test_for_speech_removes_markdown_emoji_and_ssml_chars(self):
        text = lf._for_speech("## Title\n- **Bold** & <b>tag</b> 🎉 done")
        for bad in ["#", "*", "&", "<", ">", "🎉"]:
            self.assertNotIn(bad, text)
        self.assertIn("Bold and", text)

    def test_identity_leak_pattern(self):
        leaks = ["As an AI language model, I can't.", "I'm an AI, I don't get tired.",
                 "I was trained by researchers.", "I am Nemotron.",
                 "I'm a voice assistant trained by researchers from NVIDIA."]
        fine = ["The radio was developed by several inventors.", "NVIDIA makes graphics cards.",
                "I'm happy to help!", "The vaccine was developed by researchers at Oxford."]
        for t in leaks:
            self.assertTrue(lf._IDENTITY_LEAK_PATTERN.search(t), t)
        for t in fine:
            self.assertFalse(lf._IDENTITY_LEAK_PATTERN.search(t), t)

    def test_placeholders_count_as_empty(self):
        os.environ["SEARCH_API_KEY"] = "paste-your-tavily-key-here"
        try:
            self.assertEqual(lf._setting("SEARCH_API_KEY"), "")
        finally:
            del os.environ["SEARCH_API_KEY"]


class ModelFileTests(unittest.TestCase):
    def test_interaction_model_matches_code(self):
        path = os.path.join(ROOT, "skill-package", "interactionModels", "custom", "en-US.json")
        with open(path, encoding="utf-8") as f:
            model = json.load(f)
        names = {i["name"] for i in model["interactionModel"]["languageModel"]["intents"]
                 if not i["name"].startswith("AMAZON.")}
        self.assertEqual(names, set(lf.QUESTION_INTENT_PREFIXES))


if __name__ == "__main__":
    unittest.main()
