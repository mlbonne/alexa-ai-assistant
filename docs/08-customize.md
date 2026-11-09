# 8. Customize

All settings are in `lambda/config.py`. Behavior lives in `lambda/lambda_function.py`.
After changing either, deploy again.

## Persona

Set `ASSISTANT_NAME` in `config.py` (e.g. `"Nova"`). The skill then:

1. adds identity rules to the system prompt;
2. sends a few **example exchanges** before the real conversation. Small models follow examples
   far better than rules. With rules alone, our test model kept saying "I'm Nemotron, a
   language model". The examples end with a system note saying they're only style examples;
   without it, the model treated them as real ("How did that job interview go?");
3. checks every reply with `_IDENTITY_LEAK_PATTERN` and **removes only the out-of-character
   sentences** ("I'm an AI", "I was trained by..."). The rest of the answer is kept. The
   pattern only matches **first-person** self-descriptions. An earlier, broader version ("language
   model" anywhere) hid perfectly good answers like "ChatGPT is a large language model", which
   users heard as refusals.

To change the personality itself (warmer, funnier, more formal...), edit `BASE_PROMPT`.
Ideas that worked well for us:

- describe the personality in a few adjectives;
- tell it not to assume the user's gender;
- tell it not to open with greetings or close with goodbyes unless the user does;
- in gendered languages, say which grammatical gender the assistant uses for itself.

Greetings and goodbyes are picked at random from `GREETINGS` and `GOODBYES`.

> Personal use only. A skill published to the Alexa store can't present itself as Alexa.

## Language

To run the skill in another language (for example Portuguese):

1. **Console:** add the locale (or create the skill with it) and set your Echo to that language.
2. **Interaction model:** copy `scripts/build_interaction_model.py` and translate
   `INVOCATION_NAME`, the leading words in `SEARCHQUERY_INTENTS` and the `CATCH_ALL_VALUES`.
   Set `LOCALE` (e.g. `"pt-BR"`) and run it. Keep the intent **names** the same, or update both
   files together.
3. **`config.py`:** set `WIKIPEDIA_LANG` (e.g. `"pt"`).
4. **`lambda_function.py`:** translate:
   - `WIKIPEDIA_TITLE_PROMPT` and its examples (they teach the model how to name articles in
     that language's Wikipedia);
   - `FACT_INTENTS`, `EXPLAIN_INTENTS` and the patterns in `_should_search`,
     `_should_use_wikipedia` and `_CURRENT_ROLE_PATTERN`;
   - `QUESTION_INTENT_PREFIXES` (the words put back in front of questions);
   - `BASE_PROMPT` (also add "always answer in <language>");
   - `GREETINGS`, `GOODBYES` and every spoken message;
   - the search word lists;
   - `_today()`, which uses English day and month names;
   - the persona examples.
5. **Check the model's quality** in your language with `scripts/benchmark_models.py --prompt "..."`.
   Some fast models are much weaker outside English.

Tip: build intents for the question words people actually start sentences with in that language
("quem", "qual", "o que", "por que"…). Watch out for words that differ only by case or spacing,
such as "por que" and "porque": intent names must stay unique **without regard to case**.

## Provider and model

Change `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY`. No code changes are needed for any
OpenAI-compatible API. Benchmark first ([step 2](02-choose-a-fast-model.md)).

## Timing

At the top of `lambda_function.py`:

| Constant | Default | Meaning |
|---|---|---|
| `ALEXA_DEADLINE_SECONDS` | 7.3 | Total budget for search + model |
| `REQUEST_TIMEOUT_SECONDS` | 6.5 | Max for the model call alone |
| `SEARCH_TIMEOUT_SECONDS` | 2.5 | Max for the search |
| `MAX_TOKENS` | 400 | Answer length cap (spoken answers should be short) |
| `MAX_HISTORY_MESSAGES` | 6 | Messages remembered (3 exchanges). Keep it short: small models copy the style of their own earlier replies, so one evasive answer can become a habit |
| `LLM_RETRY_RESERVE_SECONDS` | 2.5 | Time kept for one retry when the first model call gets stuck |

The OpenAI client runs with `max_retries=0`. Automatic retries would blow the 8-second window.
