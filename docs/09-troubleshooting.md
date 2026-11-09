# 9. Troubleshooting

Every entry below is a problem we actually hit while building this.

## The skill says...

| It says | Cause | Fix |
|---|---|---|
| "My API key is not configured" | `config.py` is missing, in the wrong folder, or still has the placeholder | Create `lambda/config.py` next to `lambda_function.py`; Save; Deploy |
| "Authentication error: the API key was rejected" (HTTP 401) | Wrong or expired key, or a stray space | Copy the key again. NVIDIA keys expire after 6 months |
| "Your AI provider account is out of credit" (HTTP 402) | Paid model with no balance | Add credit, or switch to a free model |
| "I've used up today's free quota..." (HTTP 429, long wait) | Daily free cap reached (e.g. 50/day on some routers) | Wait for the reset, add credit, or switch to a provider without a daily cap |
| "That was a lot of questions in a row..." (HTTP 429, short wait) | Per-minute rate limit | Wait the given seconds |
| "Error: model or address not found" (HTTP 404) | Wrong model ID or base URL, **or** the model is listed but not deployed | `python scripts/benchmark_models.py --list` and try another |
| "The model took too long to answer" | The model is too slow or queued | Benchmark and pick a faster model (step 2) |
| "The model returned an empty answer" | A **reasoning model** spent all its tokens thinking | Keep `LLM_REASONING_EFFORT = "none"`; or raise `MAX_TOKENS`; or switch models |
| "The model provider returned error 400" | Provider rejects `reasoning_effort` | Set `LLM_REASONING_EFFORT = ""` |

## Alexa says...

| Symptom | Cause | Fix |
|---|---|---|
| "There was a problem with the requested skill's response" | The skill took **> ~8 s**, or returned invalid output | Faster model; check CloudWatch Logs. (Characters like `&`, `<`, `>` in a reply break Alexa's speech markup; `_for_speech` strips them.) |
| It doesn't find the skill on the Echo | Echo language ≠ skill locale, different Amazon account, or testing is Off | Alexa app → device → Language; same account; Test tab → Development |
| "I don't know that" / a regular-Alexa answer in the middle of a conversation | You said "Alexa, ..." while the skill was open, so it left the skill | Just speak during the listening window, without the wake word |
| A one-shot question fails ("Alexa, ask smart helper ...") | The words after the skill name don't start with a known leading word | Start with who/what/why/how..., or "tell me", "search for"... |

## Building the interaction model fails

| Error | Fix |
|---|---|
| `DuplicateIntentName ... cannot be defined more than once` | Intent names are compared without regard to case. Rename one |
| `InvalidSlotTypeReference ... cannot reference more than one slot type` | The same slot name is used with two types. Rename one (the catch-all uses `phrase`) |
| A sample with only `{query}` is rejected | `AMAZON.SearchQuery` needs a fixed word before it. Use a custom slot type for catch-alls |

`python scripts/build_interaction_model.py` checks all three before you upload.

## The model's behavior

| Symptom | Fix |
|---|---|
| It introduces itself by its model name | Set `ASSISTANT_NAME` (persona examples + leak guard) |
| It reads out asterisks or emojis | Already handled by `_for_speech`. Add any other symbols you hear |
| It states made-up "current" numbers | Add a Tavily key. Without one, the prompt already tells it to flag possibly outdated info |
| It repeats an unprompted disclaimer | Tighten `BASE_PROMPT`: rules phrased as "only if the user asks..." work best |
| Answers are cut off mid-sentence | Raise `MAX_TOKENS` (keep spoken answers short, though) |

## Web search

| Symptom | Fix |
|---|---|
| Search always fails with HTTP 400 | An unsupported parameter combination (e.g. `country` with `search_depth: "fast"`). The log shows Tavily's message |
| Answers based on old pages | Use `search_depth: "basic"` and avoid the `language` filter (see [step 7](07-web-search.md)) |
| It searches for things that don't need it | Narrow `_CURRENT_INFO_PATTERN` / `_TIME_WORDS_PATTERN` |

## Tooling

| Symptom | Fix |
|---|---|
| PowerShell: "running scripts is disabled on this system" for `ask` | Use `ask.cmd` |
| `git clone` of the hosted repo asks for a username, or says `ask-resources.json not exists` | Run git inside a folder with `ask-resources.json` + `.ask/ask-states.json` (step 5.3) |
| Pushing to `dev` didn't deploy | Also push to `master` (`git push origin dev:master`) |
| The console blocks your automation | Amazon blocks AI agents on the console. Use the ASK CLI |
| A setting you changed came back | An editor saved an old open copy of `config.py`. Reopen the file before editing |
