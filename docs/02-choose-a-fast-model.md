# 2. Choose a fast model

## Why speed matters more than "smartness"

Alexa waits about **8 seconds** for your skill. After that it says *"There was a problem with
the requested skill's response"*, and nothing your code does later can help.
**Progressive responses** (the "let me think..." you'll hear) improve the experience but do
**not** extend the 8 seconds.

With web search, the budget is roughly: search up to 2.5 s, plus the model, plus a safety
margin. So you want a model whose answers **consistently arrive in under ~4 seconds**.

## Benchmark candidates

Put your key in `lambda/config.py` first (copy `config.example.py`), or export it as
`LLM_API_KEY`. Then run:

```bash
pip install "openai>=1.30,<2"
python scripts/benchmark_models.py --list
python scripts/benchmark_models.py model-a model-b model-c
```

Example output (NVIDIA free tier, November 2026):

```
model                                           median    worst problems  verdict
nvidia/nemotron-3.5-lightning-30b-a3b             0.8s     1.5s        0  GOOD
moonshotai/kimi-k2.6                                 -        -        3  NO
```

What we found when we tested 9 free NVIDIA models:

- Only **`nvidia/nemotron-3.5-lightning-30b-a3b`** was fast enough (0.4–3 s).
- DeepSeek, Gemma, GPT-OSS, Mistral Large and GLM all took **over 15 seconds** (they queue on
  the free tier). MiniMax took 11–12 s.
- Some models are listed in the catalog but return **404** (not actually deployed).

Run the benchmark **a few times, at different hours**: free endpoints get busier at peak times.
Then set `LLM_MODEL` in `config.py` to the winner.

## Watch out for "reasoning" models

Some models "think" before answering. With a token cap, they can spend **the whole budget
thinking** and return an **empty answer**. The benchmark flags this as
`<EMPTY - likely spent its budget reasoning>`.

The skill sends `reasoning_effort: "none"` to turn thinking off, which works on most providers.
If yours rejects it with HTTP 400, set `LLM_REASONING_EFFORT = ""` in `config.py`.

## Small, fast models have trade-offs

Fast models are usually small. In our testing the fast model was great for questions and
conversation, but:

- it fumbled tasks with strict rules (acrostic poems skipped letters);
- it sometimes invented small details;
- it introduced itself by its own model name unless given a persona (see [step 8](08-customize.md)).

If you have a paid key, a larger "flash"-class model from a commercial provider usually gives
better answers within the time limit. Benchmark it the same way.

Next: [3. Create the skill](03-create-the-skill.md)
