"""Generate skill-package/interactionModels/custom/en-US.json and check it against the rules
that make Alexa reject a model. Run it after editing the lists below:

    python scripts/build_interaction_model.py

To localize, copy this script, translate INVOCATION_NAME and the words below (and the matching
QUESTION_INTENT_PREFIXES in lambda/lambda_function.py), and write e.g. pt-BR.json.
"""
import json
import os
import sys

LOCALE = "en-US"
INVOCATION_NAME = "smart helper"  # what users say after "Alexa, open ..."; 2+ words, lower case

# Intent -> sample phrases that start with fixed "carrier" words. AMAZON.SearchQuery slots
# must have at least one fixed word before them, so each leading word gets its own intent and
# the code puts the word back in front of the captured text.
SEARCHQUERY_INTENTS = {
    "QueryIntent": ["ask {query}", "question {query}", "tell me {query}", "tell me about {query}",
                    "explain {query}", "i want to know {query}", "talk about {query}"],
    "QuestionWhoIntent": ["who {query}"],
    "QuestionWhosIntent": ["who's {query}"],
    "QuestionWhatIntent": ["what {query}"],
    "QuestionWhatsIntent": ["what's {query}"],
    "QuestionWhenIntent": ["when {query}"],
    "QuestionWhereIntent": ["where {query}"],
    "QuestionWhyIntent": ["why {query}"],
    "QuestionHowIntent": ["how {query}"],
    "QuestionWhichIntent": ["which {query}"],
    "QuestionIsIntent": ["is {query}"],
    "QuestionAreIntent": ["are {query}"],
    "QuestionCanIntent": ["can {query}"],
    "QuestionDoIntent": ["do {query}"],
    "QuestionDoesIntent": ["does {query}"],
    "QuestionShouldIntent": ["should {query}"],
    "RequestWriteIntent": ["write {query}"],
    "RequestCreateIntent": ["create {query}"],
    "RequestMakeIntent": ["make {query}"],
    "RequestGiveMeIntent": ["give me {query}"],
    "RequestSuggestIntent": ["suggest {query}"],
    "RequestRecommendIntent": ["recommend {query}"],
    "RequestTranslateIntent": ["translate {query}"],
    "RequestSummarizeIntent": ["summarize {query}"],
    "RequestCalculateIntent": ["calculate {query}"],
    "RequestDescribeIntent": ["describe {query}"],
    "SearchIntent": ["search {query}", "search for {query}", "search the web for {query}"],
    "SearchLookUpIntent": ["look up {query}"],
    "SearchFindIntent": ["find {query}", "find out {query}"],
}

# Catch-all: a custom slot type can stand alone in a sample ("{phrase}"), so it captures whole
# free-form sentences. The values only teach the model what "any sentence" looks like.
CATCH_ALL_INTENT = "FreeTalkIntent"
CATCH_ALL_SLOT = "phrase"  # must differ from "query": one slot name can't have two types
CATCH_ALL_TYPE = "FreeText"
CATCH_ALL_VALUES = [
    "i have a headache what should i do", "help me pick a gift for my mom",
    "translate good morning into spanish", "explain relativity in simple terms",
    "give me a quick dinner idea with chicken", "i have a big meeting tomorrow and i'm nervous",
    "tell me a fun fact about space", "summarize the history of the roman empire",
    "what is the difference between a virus and bacteria", "my plant has yellow leaves",
    "i want to learn to play the guitar", "make up a bedtime story about a dragon",
    "my dog won't eat", "suggest a name for my cat", "today was a rough day at work",
    "tell me more about that", "and then what", "i didn't get it can you explain again",
    "give me an example", "is that true", "keep going", "surprise me", "thank you",
]

BUILT_INS = ["AMAZON.CancelIntent", "AMAZON.HelpIntent", "AMAZON.StopIntent",
             "AMAZON.NavigateHomeIntent", "AMAZON.FallbackIntent"]


def build():
    intents = [{"name": name, "samples": []} for name in BUILT_INS]
    for name, samples in SEARCHQUERY_INTENTS.items():
        intents.append({"name": name, "slots": [{"name": "query", "type": "AMAZON.SearchQuery"}],
                        "samples": samples})
    intents.append({"name": CATCH_ALL_INTENT,
                    "slots": [{"name": CATCH_ALL_SLOT, "type": CATCH_ALL_TYPE}],
                    "samples": ["{%s}" % CATCH_ALL_SLOT]})
    types = [{"name": CATCH_ALL_TYPE, "values": [{"name": {"value": v}} for v in CATCH_ALL_VALUES]}]
    return {"interactionModel": {"languageModel": {
        "invocationName": INVOCATION_NAME, "intents": intents, "types": types}}}


def validate(model):
    problems = []
    lm = model["interactionModel"]["languageModel"]
    names = [i["name"] for i in lm["intents"]]
    lowered = [n.lower() for n in names]
    for n in set(lowered):
        if lowered.count(n) > 1:
            problems.append("intent name repeated (Alexa ignores case): %s" % n)
    slot_types, seen_samples = {}, {}
    for intent in lm["intents"]:
        for slot in intent.get("slots", []):
            slot_types.setdefault(slot["name"], set()).add(slot["type"])
        search_slots = {s["name"] for s in intent.get("slots", []) if s["type"] == "AMAZON.SearchQuery"}
        for sample in intent.get("samples", []):
            if sample in seen_samples:
                problems.append("sample '%s' used by %s and %s" % (sample, seen_samples[sample], intent["name"]))
            seen_samples[sample] = intent["name"]
            if any(sample.strip() == "{%s}" % s for s in search_slots):
                problems.append("%s: AMAZON.SearchQuery needs a fixed word before it" % intent["name"])
    for slot, types in slot_types.items():
        if len(types) > 1:
            problems.append("slot name '%s' has more than one type: %s" % (slot, sorted(types)))
    inv = lm["invocationName"]
    if inv != inv.lower() or len(inv.split()) < 2 or "alexa" in inv:
        problems.append("invocation name should be lower case, 2+ words, without 'alexa'")
    return problems


if __name__ == "__main__":
    model = build()
    problems = validate(model)
    if problems:
        print("\n".join("ERROR: " + p for p in problems))
        sys.exit(1)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "skill-package", "interactionModels", "custom", LOCALE + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("OK: wrote %s (%d intents)" % (os.path.relpath(out, root),
                                          len(model["interactionModel"]["languageModel"]["intents"])))
