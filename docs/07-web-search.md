# 7. Web search

## When the skill searches

Searching costs time (about 1 s) and a credit, so it isn't done for every question.
The skill searches when:

- you ask explicitly: **"search for..."**, **"look up..."**, **"find..."**; or
- the question mentions **current information**: news, latest, price, exchange rate, stocks,
  bitcoin, score, who won, weather, forecast, release date, election, recent years...

Generic time words (today, now, yesterday...) only trigger a search **in questions**. That way
"today was a rough day at work" gets empathy, not a wasted search. The word lists are
`_TIME_WORDS_PATTERN` and `_CURRENT_INFO_PATTERN` in `lambda_function.py`.

## Time budget

```
0 s -------- search (max 2.5 s) -------- model (rest of the budget) -------- 7.3 s | Alexa gives up ~8 s
```

If the search fails or times out, the model still answers and briefly says the information
may be outdated.

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

## Honest limitations

- **Live numbers** (exchange rates, scores of games in progress) usually come from pages that
  render the number with JavaScript. The search can't see it, so the assistant may say it
  doesn't have the live value. For those, a dedicated free API is better. A currency API, for
  example, is easy to add as another branch in `AskModelIntentHandler`.
- **Sports results** vary from search to search, and a small model can mix games up.
- **Date reasoning:** small models sometimes miss that a "coming soon" date has already passed.
- **Without any search**, the model is told not to invent current facts and to flag that they
  may be outdated. Before we added this, it confidently made up "today's" exchange rate.

General current facts (who holds an office, records, recent events) work well.

Next: [8. Customize](08-customize.md)
