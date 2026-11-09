# 1. Accounts and keys

You need three things. All have free options.

## 1.1 Amazon developer account (free)

Sign in at <https://developer.amazon.com/alexa/console/ask> with **the same Amazon account your
Echo uses**. That is what makes your development skill show up on your Echo automatically, with
no publishing step.

## 1.2 An LLM API key

> **A chat subscription is not an API key.** Paying for an AI chat app (Gemini, ChatGPT, etc.)
> does **not** give you API access. You need a separate API key from the provider's developer
> platform.

Any provider with an **OpenAI-compatible** API works. Options at the time of writing:

| Provider | Free? | Notes |
|---|---|---|
| **NVIDIA** ([build.nvidia.com](https://build.nvidia.com)) | Yes | 40 requests/minute, no daily cap. The key starts with `nvapi-` and **expires after 6 months**. Many catalog models queue for >15 s on the free tier, so benchmark first (step 2). |
| **Google Gemini** ([aistudio.google.com](https://aistudio.google.com)) | Free tier | Daily/minute limits. Free-tier prompts may be used to improve Google's products. |
| **OpenRouter-style routers** | Some free models | Free models often have small daily caps (e.g. 50/day without credit). |
| **DeepSeek, OpenAI, etc.** | Paid | Usually fractions of a cent per question. |

For NVIDIA: sign in, open any model page, click **Get API Key**, and **copy it immediately**.
It is shown only once.

## 1.3 Tavily key for web search (optional, free)

1. Go to <https://app.tavily.com> and sign up (Google/GitHub/email). No credit card is needed.
2. On the **Overview** page, copy the key under **API Keys**. It starts with `tvly-`.
3. The free plan includes **1,000 searches per month**. The skill only searches when a question
   needs current information, so that goes a long way.

Without a Tavily key the skill still works. It just tells you that current facts may be
outdated, instead of making them up.

## Keep keys private

- Keys go **only** into `lambda/config.py`, which `.gitignore` excludes. Never put them in
  `lambda_function.py`, chat messages or screenshots.
- The code on an Alexa-hosted skill lives in a **private** repository in your account, so
  `config.py` isn't public there.

Next: [2. Choose a fast model](02-choose-a-fast-model.md)
