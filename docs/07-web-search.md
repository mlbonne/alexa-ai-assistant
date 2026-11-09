# 7. Web search and Wikipedia

## Why sources matter so much

Fast models are small, and small models **get facts wrong from memory**, even old ones. In our
testing, without sources the model:
- named the wrong national football coach;
- claimed ChatGPT was made by NVIDIA;
- **invented citations** like "according to the CBF website" for searches it never did.

With sources, the same model answered the same questions correctly. So the skill grounds every
factual question in two sources, fetched **in parallel** (the total wait is the slower one, not
the sum):

| Source | Good for | Cost |
|---|---|---|
| **Wikipedia** (official API) | Established facts: history, science, geography, biographies, definitions | Free, no key |
| **Tavily web search** | Recent events, who holds a role now, results, current numbers | 1 credit per search (1,000/month free) |

The model is told which source to trust for what, and never to name a source it wasn't given.

## When sources are used

| Kind of request | Wikipedia | Web search |
|---|---|---|
| Factual questions (who/what/when/where/which, "ask...", "tell me...") | yes | yes |
| Explanations (why/how, "describe...") | yes | only with current-info words |
| "Who is the coach/president/CEO..." (a role **now**) | **no** | yes |
| Explicit "search for / look up / find..." | yes | yes (forced) |
| Free talk asking for information ("tell me about...", "news") | yes | yes |
| Free talk, venting ("today was a rough day") | no | no |
| Creative requests, arithmetic, questions about the assistant | no | no |

These rules live in `_should_search` and `_should_use_wikipedia` in `lambda_function.py`.

## Making Wikipedia find the right article

Wikipedia's search matches **words in titles, not meaning**. In our tests, "why is the sky blue"
found a *town* with those words in its name, and a "who discovered..." question found a *novel*.
Searching with keywords only didn't help.

What works is to let the model pick the article first. One tiny model call (~0.3 s) asks: *"Which
Wikipedia article answers this?"* The prompt includes a few examples (sky blue → *Rayleigh
scattering*). Then a single API call fetches that article's introduction. That found the right
article for 10 of 11 test questions in about 0.7 s total. Disambiguation pages are skipped. If
the article turns out to be off-topic, the model is told to ignore it.

Why "role now" questions skip Wikipedia: asked for "the coach of the national team", the model
suggested an article about the **previous** coach, which would have "confirmed" its outdated
memory. Those questions use web search only.

Also tested, and worse:

| Approach | Result |
|---|---|
| Tavily with `include_domains` + `"prefer"` mode | Barely changed the results. For "who was Santos Dumont" and "what is photosynthesis" it returned **no** Wikipedia page |
| Tavily **restricted** to Wikipedia | 2.8–3.8 s (too slow for Alexa's limit), often the wrong article, and 1 extra credit per question |

Set `WIKIPEDIA_LANG` in `config.py` to your skill's language. Wikimedia asks API clients to send
a descriptive `User-Agent` (`HTTP_USER_AGENT`), and it may rate-limit bursts (HTTP 429). On
failure the skill simply continues without Wikipedia.

## Tavily settings, and why

We tested several configurations in November 2026:

| Setting | Result |
|---|---|
| `search_depth: "basic"`, no language filter | **Best.** Current, dated results (Wikipedia, major news sites) in ~0.5–1.5 s, 1 credit. |
| `search_depth: "fast"` | Faster (~0.4 s), but often outdated pages. |
| `language` filter (e.g. Portuguese) | Pulled in low-quality, outdated sites ("the president is Joe Biden"). |
| `topic: "news"` | Unrelated English sports news, even for currency questions. |
| `country` + `fast` | **HTTP 400**: not supported together. |

`include_published_date` is on, and the model is told today's date. It's instructed to say when
the information is from, and never to call a number "today's" unless the snippet shows today's
date.

## Time budget

```
0 s ---- Wikipedia (title + intro) and Tavily, in parallel, max 2.5 s ---- model ---- 7.3 s | Alexa gives up ~8 s
```

If the model call gets stuck in the provider's queue (it happens on free endpoints), the first
attempt is cut early and **one retry** uses the rest of the budget.

## Budget your credits

Every factual question spends 1 Tavily credit. That's ~33 a day on the free plan. You can check
usage at <https://app.tavily.com> or with `GET https://api.tavily.com/usage`. When credits run
out, searches fail gracefully and Wikipedia still works. Each factual question also makes
**two** model calls: one to pick the Wikipedia article, one to answer. With NVIDIA's
40 requests/minute that's still about 20 questions per minute.

## Honest limitations

- **Live numbers** (exchange rates, scores of games in progress) often come from pages that render
  the number with JavaScript, which the search can't see.
- **Sports results** vary from search to search, and a small model can mix up games.
- **Date reasoning:** small models sometimes miss that a "coming soon" date has already passed.

Next: [8. Customize](08-customize.md)
