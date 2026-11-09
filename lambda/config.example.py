# Copy this file to lambda/config.py and fill it in.
# In the Alexa developer console: Code tab -> right-click the "lambda" folder -> Create File ->
# lambda/config.py, paste this, replace the placeholders, Save, Deploy.
#
# NEVER commit config.py to a public repository: it holds your keys. (.gitignore excludes it.)
# Any value that still contains "paste-your" is treated as empty.

# --- Required: the language model -----------------------------------------------------------
# Any OpenAI-compatible provider works. Default below: NVIDIA's free API (build.nvidia.com),
# 40 requests/minute, key starts with "nvapi-" and expires after 6 months.
LLM_API_KEY = "paste-your-llm-api-key-here"
LLM_BASE_URL = "https://integrate.api.nvidia.com/v1"
LLM_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"

# Other OpenAI-compatible examples (check each provider's current docs and limits):
#   Google Gemini:  LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
#   OpenRouter:     LLM_BASE_URL = "https://openrouter.ai/api/v1"
#   DeepSeek:       LLM_BASE_URL = "https://api.deepseek.com"
# Pick a model that answers in well under 8 seconds: run scripts/benchmark_models.py first.

# "none" switches off "thinking" on reasoning models (otherwise they can return empty answers).
# Set to "" if your provider rejects the parameter (you'll get an HTTP 400 error).
LLM_REASONING_EFFORT = "none"

# --- Optional: web search ---------------------------------------------------------------------
# Free Tavily key (1,000 searches/month, no credit card) from https://app.tavily.com
SEARCH_API_KEY = "paste-your-tavily-key-here"

# --- Optional: persona and clock -------------------------------------------------------------
# Give the assistant a name and it will stay in character (see docs/08-customize.md).
ASSISTANT_NAME = ""
# Used to tell the model today's date. IANA names need Python 3.9+; Alexa-hosted skills may run
# Python 3.8, where UTC_OFFSET_HOURS is used instead (it does not follow daylight saving time).
TIMEZONE = "America/New_York"
UTC_OFFSET_HOURS = -5
