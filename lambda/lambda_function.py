# -*- coding: utf-8 -*-
"""
Alexa AI Assistant: an Alexa custom skill that answers with any OpenAI-compatible LLM
and (optionally) searches the web with Tavily.

Configuration is read from environment variables OR from lambda/config.py
(Alexa-hosted skills have no environment-variable UI, so use config.py there).
See config.example.py for every setting. Never put keys in this file.
"""

import datetime
import json
import logging
import os
import random
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import openai
from openai import OpenAI

from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import is_intent_name, is_request_type
from ask_sdk_model.services.directive import Header, SendDirectiveRequest, SpeakDirective

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
try:
    import config as _local_config  # lambda/config.py (never commit it; see config.example.py)
except ImportError:
    _local_config = None

_PLACEHOLDER_MARK = "paste-your"


def _setting(name, default=""):
    """Environment variable first, then config.py, then the default. Placeholders count as empty."""
    value = os.environ.get(name)
    if value is None and _local_config is not None:
        value = getattr(_local_config, name, None)
    if value is None:
        return default
    value = str(value).strip()
    if _PLACEHOLDER_MARK in value.lower():
        return default
    return value


# Defaults: NVIDIA's free API with the one model that was fast enough for Alexa when this guide
# was written (see docs/02-choose-a-fast-model.md). Any OpenAI-compatible provider works.
API_KEY = _setting("LLM_API_KEY")
BASE_URL = _setting("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
MODEL = _setting("LLM_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
# Reasoning models can spend the whole token budget "thinking" and return an empty answer.
# "none" turns reasoning off. Set it to "" if your provider rejects the parameter.
REASONING_EFFORT = _setting("LLM_REASONING_EFFORT", "none")

# Web search (Tavily). Without a key the skill works normally, just without search.
SEARCH_API_KEY = _setting("SEARCH_API_KEY")
SEARCH_URL = "https://api.tavily.com/search"

# Wikipedia: official API, free, no key. Runs in parallel with Tavily for factual questions.
# Use the language code of your skill's locale ("en", "pt", "es", "de"...).
WIKIPEDIA_LANG = _setting("WIKIPEDIA_LANG", "en")
WIKIPEDIA_API = "https://{}.wikipedia.org/w/api.php".format(WIKIPEDIA_LANG)
WIKIPEDIA_MAX_CHARS = 1200
# Wikimedia asks API clients to send a descriptive User-Agent.
HTTP_USER_AGENT = "AlexaAIAssistant/1.0 (personal Alexa skill; low volume)"

# Persona. Leave ASSISTANT_NAME empty for a neutral assistant (see docs/08-customize.md).
ASSISTANT_NAME = _setting("ASSISTANT_NAME")
# Time zone for "today's date" in the prompt. IANA name (needs Python 3.9+) or a fixed UTC offset.
TIMEZONE = _setting("TIMEZONE", "UTC")
UTC_OFFSET_HOURS = float(_setting("UTC_OFFSET_HOURS", "0") or 0)

# ---------------------------------------------------------------------------
# Time budget. Alexa gives up after ~8 seconds and progressive responses do NOT extend that.
# ---------------------------------------------------------------------------
ALEXA_DEADLINE_SECONDS = 7.3   # total budget (search + model), measured from the handler start
REQUEST_TIMEOUT_SECONDS = 6.5  # max time for the model call alone
MIN_LLM_TIMEOUT_SECONDS = 2.0
# Free endpoints sometimes leave a request stuck in a queue for 6+ s. When there's time, the first
# attempt is cut early and a second attempt uses the rest of the budget.
LLM_RETRY_RESERVE_SECONDS = 2.5
LLM_TIMEOUT_SPEECH = "The model took too long to answer. Please try again."
WIKIPEDIA_TITLE_TIMEOUT_SECONDS = 1.5
SEARCH_TIMEOUT_SECONDS = 2.5
SEARCH_MAX_RESULTS = 4
SEARCH_MAX_CONTEXT_CHARS = 2200
MAX_TOKENS = 400
# Only the last 3 exchanges. Small models copy the style of their own earlier replies, and with a
# long history one evasive answer ("you can check a website...") turned into a habit.
MAX_HISTORY_MESSAGES = 6

# ---------------------------------------------------------------------------
# Prompt and persona
# ---------------------------------------------------------------------------
BASE_PROMPT = (
    "You are a friendly, warm and helpful voice assistant running on an Amazon Echo. "
    "Your answers are spoken aloud, so keep them natural and conversational. "
    "For questions, be concise: 2 to 4 short sentences. For creative requests (poems, stories, "
    "jokes), fulfil the request but keep it short: at most about 8 lines or 6 sentences. "
    "Never use markdown, bullet points, numbered lists, emojis or symbols that don't read well "
    "aloud; separate lines of a poem only with line breaks. If you don't know, say so. "
    "Get straight to the point: don't open with greetings or close with goodbyes unless the "
    "user is greeting you or saying goodbye. Don't assume the user's gender. "
    "You can't control devices, play music, set alarms or buy things. Only mention this if the "
    "user asks for one of those; then kindly say they can say \"stop\" and ask again. "
    "Always answer the question directly with the best answer you have. Never tell the user to "
    "look it up on websites, search engines or books, and never say you don't have access to "
    "information unless you truly don't know the answer. "
    "Sometimes you receive sources gathered just now (Wikipedia and/or web search results): when "
    "you do, base your answer on them and prefer them over what you already know. NEVER invent "
    "sources: only say \"according to X\" if X appears in the sources given for this question; "
    "without sources, don't name any website, newspaper or institution. Never read web addresses "
    "aloud, and don't comment on whether you searched; just answer."
)


def _persona_prompt():
    if not ASSISTANT_NAME:
        return ""
    return (
        " Your name is {name}. If asked who you are or what you are, say you are {name}, the voice "
        "assistant. Never introduce yourself by the name of an AI model, never say you are a "
        "language model or an AI, and never talk about who trained you."
    ).format(name=ASSISTANT_NAME)


# Small models follow examples much better than rules. These go before the real conversation.
def _persona_examples():
    if not ASSISTANT_NAME:
        return []
    return [
        {"role": "user", "content": "what's your name?"},
        {"role": "assistant", "content": "I'm {}! Happy to chat with you.".format(ASSISTANT_NAME)},
        {"role": "user", "content": "are you a robot? who made you?"},
        {"role": "assistant", "content": "I'm {}, your voice assistant. I never get tired, and I "
                                         "love a good conversation!".format(ASSISTANT_NAME)},
        {"role": "system", "content": "The messages above were only examples of your style. They "
                                      "did not really happen. The real conversation starts now."},
    ]


# Safety net: FIRST-PERSON sentences where the model breaks character. Only those sentences are
# removed (see _strip_identity_leaks). A broad pattern like "language model" also hid good
# answers: "what is ChatGPT?" -> "ChatGPT is a large language model..." looked like a leak.
_IDENTITY_LEAK_PATTERN = re.compile(
    r"\bas an?\s+(?:ai\s+)?(?:large\s+)?language model\b"
    r"|\bi(?:['’]m| am)\s+(?:an?\s+)?(?:(?:large\s+)?language model|ai|artificial intelligence|chatbot|bot|robot|model)\b"
    r"|\bi\s+(?:was|have been|['’]ve been)\s+(?:trained|created|developed|built|made)\s+by\b"
    r"|\bassistant\s+(?:that was\s+|who was\s+)?(?:trained|created|developed|built|made)\s+by\b"
    r"|\bi(?:['’]m| am)\s+(?:nemotron|llama|qwen|deepseek|gemma|mistral|chatgpt|gpt|claude|gemini)\b",
    re.IGNORECASE,
)


def _persona_fallback():
    return "I'm {}, your voice assistant! How can I help you?".format(ASSISTANT_NAME)


def _strip_identity_leaks(text):
    """Drop only the out-of-character sentences and keep the rest of the answer."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = [s for s in sentences if not _IDENTITY_LEAK_PATTERN.search(s)]
    if len(kept) == len(sentences):
        return text
    logger.info("Removed %d out-of-character sentence(s).", len(sentences) - len(kept))
    return " ".join(kept).strip() or _persona_fallback()


GREETINGS = [
    "Hi! It's good to hear from you. Ask me anything.",
    "Hello! I'm here to help. What would you like to talk about?",
    "Hey there! What do you want to know?",
]
GOODBYES = ["Goodbye! It was lovely talking with you.", "Bye! Call me anytime.", "See you soon!"]


def _now():
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
        return datetime.datetime.now(ZoneInfo(TIMEZONE))
    except Exception:  # noqa: BLE001 - Python 3.8 or unknown zone: use the fixed offset
        return datetime.datetime.utcnow() + datetime.timedelta(hours=UTC_OFFSET_HOURS)


def _today():
    now = _now()
    return "{}, {} {}, {}".format(now.strftime("%A"), now.strftime("%B"), now.day, now.year)


def _system_prompt():
    return "{}{} Today is {}.".format(BASE_PROMPT, _persona_prompt(), _today())


# The client is only created when there is a key, so a missing config doesn't crash cold starts.
_client = None
if API_KEY:
    # max_retries=0: automatic retries would blow Alexa's ~8 second window.
    _client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS,
                     max_retries=0)
else:
    logger.error("LLM_API_KEY is not set. Create lambda/config.py (see config.example.py).")


def _send_progressive_response(handler_input, text):
    """Say something right away so the user doesn't wait in silence. Best effort."""
    try:
        request_id = handler_input.request_envelope.request.request_id
        directive_service = handler_input.service_client_factory.get_directive_service()
        directive_service.enqueue(SendDirectiveRequest(
            header=Header(request_id=request_id), directive=SpeakDirective(speech=text)))
    except Exception as exc:  # noqa: BLE001
        logger.info("Progressive response not sent: %s", exc)


# ---------------------------------------------------------------------------
# Web search
# ---------------------------------------------------------------------------
def _normalize(text):
    """Lower case, no accents."""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


# Generic time words only count in questions: "today was a rough day" is venting, not a request
# for information, and shouldn't spend a search.
_TIME_WORDS_PATTERN = re.compile(
    r"\b(today|tonight|now|right now|currently|current|yesterday|tomorrow|"
    r"this (week|month|year))\b")
_CURRENT_INFO_PATTERN = re.compile(
    r"\b(latest|most recent|recent(ly)?|news|headlines?|happened|happening|"
    r"prices?|how much (is|does)|exchange rate|stocks?|bitcoin|crypto\w*|"
    r"scores?|who (won|wins|is winning)|standings|weather|forecast|going to rain|temperature|"
    r"released?|release date|premieres?|came out|elections?|"
    r"20(2[5-9]|3\d))\b")


def _needs_search(query, is_question=True):
    text = _normalize(query)
    if _CURRENT_INFO_PATTERN.search(text):
        return True
    return is_question and bool(_TIME_WORDS_PATTERN.search(text))


# Factual questions ALWAYS search. Small, fast models get many facts wrong from memory (even old
# ones) and invent sources; with search they answer from real results. Intent names must match
# QUESTION_INTENT_PREFIXES below.
FACT_INTENTS = {
    "QueryIntent", "QuestionWhoIntent", "QuestionWhosIntent", "QuestionWhatIntent",
    "QuestionWhatsIntent", "QuestionWhenIntent", "QuestionWhereIntent", "QuestionWhichIntent",
    "QuestionIsIntent", "QuestionAreIntent", "QuestionCanIntent", "QuestionDoIntent",
    "QuestionDoesIntent",
}
# Explanations: Wikipedia helps (free), web search only with current-info signals.
EXPLAIN_INTENTS = {"QuestionWhyIntent", "QuestionHowIntent", "RequestDescribeIntent"}
_MATH_PATTERN = re.compile(
    r"\d\s*(times|x|plus|minus|divided by|to the power of|\+|-|\*|/)\s*\d|square root|percent of")
_ABOUT_ASSISTANT_PATTERN = re.compile(r"\b(you|your|yours|yourself)\b")
_INFO_REQUEST_PATTERN = re.compile(
    r"^(tell me|talk|explain)(\s+more)?\s+(about|of)\b|\bwhat do you know about\b|\bnews\b")
# "Who is the coach / president / CEO..." asks who holds a role NOW. The model suggested
# Wikipedia articles about outdated people, so these skip Wikipedia and use web search only.
_CURRENT_ROLE_PATTERN = re.compile(
    r"\b(current|currently|now|today)\b|"
    r"^(is|are)?\s*(the\s+)?(head\s+)?(coach|manager|president|prime minister|minister|governor|"
    r"mayor|ceo|owner|director|pope|king|queen|leader|champions?)\b")


def _about_assistant(text):
    # "do you know who won..." is about the world, not about the assistant.
    text = re.sub(r"^(you know|you think)\s+", "", text)
    return bool(_ABOUT_ASSISTANT_PATTERN.search(text))


def _should_search(intent_name, slot_value):
    """Is it worth a web search? slot_value is the text without the intent's leading word."""
    if intent_name in FORCE_SEARCH_INTENTS:
        return True
    text = _normalize(slot_value)
    if _MATH_PATTERN.search(text) or _about_assistant(text):
        return False
    if intent_name in FACT_INTENTS:
        return True
    if intent_name == CATCH_ALL_INTENT:
        return bool(_INFO_REQUEST_PATTERN.search(text)) or _needs_search(slot_value, False)
    return _needs_search(slot_value, True)


def _should_use_wikipedia(intent_name, slot_value):
    text = _normalize(slot_value)
    if _MATH_PATTERN.search(text) or _about_assistant(text) or _CURRENT_ROLE_PATTERN.search(text):
        return False
    return (intent_name in FACT_INTENTS or intent_name in EXPLAIN_INTENTS
            or intent_name in FORCE_SEARCH_INTENTS
            or (intent_name == CATCH_ALL_INTENT and bool(_INFO_REQUEST_PATTERN.search(text))))


# Wikipedia's search matches title words, not meaning ("why is the sky blue" can find a town or a
# song). So the model first names the article that answers the question (~0.3 s).
WIKIPEDIA_TITLE_PROMPT = (
    "Give the title of the Wikipedia article (language code: {lang}) that best answers the "
    "question. Reply with ONLY the title: no quotes, no question mark, no explanation. Never "
    "repeat the question; name the topic. If the question is about who holds a role NOW (coach, "
    "president, CEO, current champion), give the article about the role or the institution, "
    "never a person's name. If no article makes sense (chit-chat, creative request, arithmetic), "
    "reply NONE.\n"
    "Examples:\n"
    "why is the sky blue -> Rayleigh scattering\n"
    "who discovered penicillin -> Penicillin\n"
    "who is the president of france -> President of France\n"
    "who is the ceo of apple -> Apple Inc.\n"
    "thanks -> NONE"
)


def _wikipedia_title(query, timeout):
    """Ask the model which article to look up. Returns a search term, or None for no article."""
    if _client is None:
        return query
    try:
        completion = _client.chat.completions.create(
            model=MODEL, max_tokens=20, temperature=0, timeout=timeout,
            messages=[{"role": "system", "content": WIKIPEDIA_TITLE_PROMPT.format(lang=WIKIPEDIA_LANG)},
                      {"role": "user", "content": query}],
            extra_body={"reasoning_effort": REASONING_EFFORT} if REASONING_EFFORT else None)
    except Exception as exc:  # noqa: BLE001 - fall back to searching with the question itself
        logger.info("Wikipedia title unavailable: %r", exc)
        return query
    title = (completion.choices[0].message.content or "").strip().split("\n")[0]
    title = title.strip(" \"'.?").split("->")[-1].strip()
    if not title or title.upper().startswith("NONE"):
        return None
    return title


def _wikipedia_intro(query, timeout):
    """Find the article that answers the question and return its intro, or None.

    Two steps: the model names the article, then one API call (generator=search) returns the
    intro text. Disambiguation pages are skipped. Any failure (timeout, HTTP 429...) -> None.
    """
    started = time.monotonic()
    term = _wikipedia_title(query, min(WIKIPEDIA_TITLE_TIMEOUT_SECONDS, timeout))
    remaining = timeout - (time.monotonic() - started)
    if not term or remaining < 0.3:
        return None
    params = {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrsearch": term, "gsrlimit": "3",
        "prop": "extracts|pageprops", "ppprop": "disambiguation",
        "exintro": "1", "explaintext": "1", "exchars": str(WIKIPEDIA_MAX_CHARS), "redirects": "1",
    }
    request = urllib.request.Request(WIKIPEDIA_API + "?" + urllib.parse.urlencode(params),
                                     headers={"User-Agent": HTTP_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=remaining) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Wikipedia failed after %.2fs: %r", time.monotonic() - started, exc)
        return None
    pages = sorted(data.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
    for page in pages:
        if "disambiguation" in (page.get("pageprops") or {}):
            continue
        extract = " ".join((page.get("extract") or "").split())
        if extract:
            logger.info("Wikipedia: '%s' in %.2fs", page.get("title"), time.monotonic() - started)
            return "[Wikipedia article \"{}\"] {}".format(page.get("title"), extract)
    return None


def _web_search(query, timeout):
    """Search with Tavily. Returns context text for the model, or None on failure."""
    payload = {
        "query": query,
        # "basic" costs 1 credit and took ~0.5-1.5 s in testing. "fast" and the "language" filter
        # returned outdated pages; topic "news" returned unrelated English sports news;
        # "country" is rejected (HTTP 400) together with "fast".
        "search_depth": "basic",
        "max_results": SEARCH_MAX_RESULTS,
        "chunks_per_source": 2,
        "include_answer": False,
        "topic": "general",
        "include_published_date": True,
    }
    request = urllib.request.Request(
        SEARCH_URL, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": "Bearer {}".format(SEARCH_API_KEY),
                 "Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:  # noqa: BLE001
            detail = ""
        logger.error("Search failed: HTTP %s %s", exc.code, detail)
        return None
    except Exception as exc:  # noqa: BLE001 - timeout, network...
        logger.error("Search failed after %.2fs: %r", time.monotonic() - started, exc)
        return None

    lines = []
    for index, item in enumerate(data.get("results") or [], start=1):
        content = " ".join((item.get("content") or "").split())
        if not content:
            continue
        site = re.sub(r"^https?://(www\.)?", "", item.get("url") or "").split("/")[0]
        dated = " ({})".format(item["published_date"]) if item.get("published_date") else ""
        lines.append("[{}] {} - {}{}: {}".format(index, item.get("title") or "", site, dated, content))
    logger.info("Search: %d results in %.2fs", len(lines), time.monotonic() - started)
    return "\n".join(lines)[:SEARCH_MAX_CONTEXT_CHARS] if lines else None


def _sources_context(wiki, results):
    parts = [
        "Sources gathered just now to answer the question. Today is {}.".format(_today()),
        "For established facts (history, science, geography, biographies, definitions), trust the "
        "Wikipedia excerpt first, if it is about the topic asked. For recent events, who holds a "
        "role now, results and current numbers, prefer the most recent web results. If the "
        "Wikipedia excerpt is about something else, ignore it.",
    ]
    if results:
        parts.append(
            "Careful: web snippets may come from old pages. If a snippet has a date, use it and say "
            "when the information is from. Never call a number (price, rate, score) today's unless "
            "the snippet clearly shows today's date. Compare every date with today's: if something "
            "was going to happen on a date that has passed, say it already happened.")
    if wiki:
        parts.append(wiki)
    if results:
        parts.append("Web search results:\n" + results)
    return "\n".join(parts)


NO_SEARCH_CONTEXT = (
    "You do NOT have access to current information right now. Don't make up today's prices, "
    "scores or news; say what you know and add, in one short sentence, that it may be outdated.")

# ---------------------------------------------------------------------------
# Talking to the model
# ---------------------------------------------------------------------------
_EMOJI_PATTERN = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF‍️⭐⭕]+")


def _for_speech(text):
    """Make model output safe to speak.

    Removes markdown (some models use it even when told not to) and emojis, and removes the
    SSML special characters & < >, which would make Alexa reject the whole response.
    """
    text = re.sub(r"\*\*|__|`+|\*", "", text)        # bold, italics, code
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)     # headings
    text = re.sub(r"(?m)^\s*[-•]\s+", "", text)       # bullets
    text = text.replace("&", " and ").replace("<", " ").replace(">", " ")
    text = _EMOJI_PATTERN.sub("", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _rate_limit_message(exc):
    """Explain an HTTP 429, using the provider's retry hint when there is one."""
    retry = None
    response = getattr(exc, "response", None)
    if response is not None:
        retry = response.headers.get("retry-after")
    body = exc.body if isinstance(getattr(exc, "body", None), dict) else {}
    error = body.get("error") if isinstance(body.get("error"), dict) else body
    metadata = error.get("metadata") if isinstance(error.get("metadata"), dict) else {}
    retry = metadata.get("retry_after_seconds", retry)
    try:
        retry = int(float(retry))
    except (TypeError, ValueError):
        retry = None
    if retry and retry > 120:
        return "I've used up today's free quota with my AI provider. Please try again later."
    if retry:
        return "That was a lot of questions in a row. Wait about {} seconds and ask again.".format(retry)
    return "My AI provider is busy or out of credit right now. Please try again later."


def _ask_llm(history, context=None, timeout=REQUEST_TIMEOUT_SECONDS):
    """Ask the model. Returns (ok, text). On errors the text says WHAT went wrong, out loud,
    so you can diagnose problems from the Echo without opening CloudWatch."""
    if _client is None:
        return False, "My API key is not configured. Please check the config dot py file."

    messages = [{"role": "system", "content": _system_prompt()}] + _persona_examples()
    if context:
        messages.append({"role": "system", "content": context})
    messages += history
    started = time.monotonic()
    try:
        completion = _client.chat.completions.create(
            model=MODEL, messages=messages, max_tokens=MAX_TOKENS, timeout=timeout,
            extra_body={"reasoning_effort": REASONING_EFFORT} if REASONING_EFFORT else None)
        logger.info("LLM answered in %.2fs (%s)", time.monotonic() - started, MODEL)
        text = _for_speech(completion.choices[0].message.content or "")
        if ASSISTANT_NAME:
            text = _strip_identity_leaks(text)
        if not text:
            return False, "The model returned an empty answer. Try asking another way."
        return True, text
    except openai.APITimeoutError:
        speak = LLM_TIMEOUT_SPEECH
    except openai.AuthenticationError:
        speak = "Authentication error: the API key was rejected. Check the key in config dot py."
    except openai.PermissionDeniedError:
        speak = "Permission error: the key can't use this model, or the account is out of credit."
    except openai.NotFoundError:
        speak = "Error: model or address not found. Check the model and base URL in config dot py."
    except openai.RateLimitError as exc:
        speak = _rate_limit_message(exc)
    except openai.APIConnectionError:
        speak = "Connection error: I couldn't reach the model's server."
    except openai.APIStatusError as exc:
        if exc.status_code == 402:
            speak = "Your AI provider account is out of credit. Add credit to keep going."
        else:
            speak = "The model provider returned error {}.".format(exc.status_code)
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error: %r", exc, exc_info=True)
        speak = "Unexpected error calling the model: {}.".format(type(exc).__name__)
    logger.error("LLM call failed (%s / %s) after %.2fs: %s",
                 BASE_URL, MODEL, time.monotonic() - started, speak)
    return False, speak


# ---------------------------------------------------------------------------
# Intents. Names must match skill-package/interactionModels/custom/en-US.json.
# Alexa removes the leading word from the slot value ("who" in "who invented the radio"),
# so each intent puts its word back before the question goes to the model.
# ---------------------------------------------------------------------------
QUESTION_INTENT_PREFIXES = {
    "QueryIntent": "",
    "QuestionWhoIntent": "who",
    "QuestionWhosIntent": "who's",
    "QuestionWhatIntent": "what",
    "QuestionWhatsIntent": "what's",
    "QuestionWhenIntent": "when",
    "QuestionWhereIntent": "where",
    "QuestionWhyIntent": "why",
    "QuestionHowIntent": "how",
    "QuestionWhichIntent": "which",
    "QuestionIsIntent": "is",
    "QuestionAreIntent": "are",
    "QuestionCanIntent": "can",
    "QuestionDoIntent": "do",
    "QuestionDoesIntent": "does",
    "QuestionShouldIntent": "should",
    "RequestWriteIntent": "write",
    "RequestCreateIntent": "create",
    "RequestMakeIntent": "make",
    "RequestGiveMeIntent": "give me",
    "RequestSuggestIntent": "suggest",
    "RequestRecommendIntent": "recommend",
    "RequestTranslateIntent": "translate",
    "RequestSummarizeIntent": "summarize",
    "RequestCalculateIntent": "calculate",
    "RequestDescribeIntent": "describe",
    # Explicit search requests: the verb is dropped and the search is forced.
    "SearchIntent": "",
    "SearchLookUpIntent": "",
    "SearchFindIntent": "",
    # Catch-all: the whole sentence, no leading word required.
    "FreeTalkIntent": "",
}
FORCE_SEARCH_INTENTS = {name for name in QUESTION_INTENT_PREFIXES if name.startswith("Search")}
CATCH_ALL_INTENT = "FreeTalkIntent"
# Alexa won't let one slot name have two different types, so the catch-all uses "phrase".
SLOT_NAMES = ("query", "phrase")


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        handler_input.attributes_manager.session_attributes["history"] = []
        return (handler_input.response_builder.speak(random.choice(GREETINGS))
                .ask("Go ahead, I'm listening.").response)


class AskModelIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        request = handler_input.request_envelope.request
        return (is_request_type("IntentRequest")(handler_input)
                and request.intent.name in QUESTION_INTENT_PREFIXES)

    def handle(self, handler_input):
        started = time.monotonic()
        intent = handler_input.request_envelope.request.intent
        slots = intent.slots or {}
        query = None
        for slot_name in SLOT_NAMES:
            if slots.get(slot_name) is not None and slots[slot_name].value:
                query = slots[slot_name].value
                break
        slot_value = query or ""
        prefix = QUESTION_INTENT_PREFIXES.get(intent.name, "")
        if query and prefix:
            query = "{} {}".format(prefix, query)
        if not query:
            speak = "Sorry, I didn't catch that. Could you say it again?"
            return handler_input.response_builder.speak(speak).ask(speak).response

        forced = intent.name in FORCE_SEARCH_INTENTS
        is_question = intent.name != CATCH_ALL_INTENT or query.rstrip().endswith("?")
        wants_current_info = forced or _needs_search(query, is_question)
        do_search = bool(SEARCH_API_KEY) and _should_search(intent.name, slot_value)
        use_wiki = _should_use_wikipedia(intent.name, slot_value)

        _send_progressive_response(
            handler_input, "Let me look that up..." if (do_search or use_wiki) else "Hmm, let me think...")

        context, notice = None, ""
        if do_search or use_wiki:
            remaining = ALEXA_DEADLINE_SECONDS - (time.monotonic() - started) - MIN_LLM_TIMEOUT_SECONDS
            budget = max(0.5, min(SEARCH_TIMEOUT_SECONDS, remaining))
            # Wikipedia and Tavily at the same time: total wait is the slower one, not the sum.
            with ThreadPoolExecutor(max_workers=2) as pool:
                wiki_future = pool.submit(_wikipedia_intro, query, budget) if use_wiki else None
                web_future = pool.submit(_web_search, query, budget) if do_search else None
                wiki = wiki_future.result() if wiki_future else None
                results = web_future.result() if web_future else None
            if wiki or results:
                context = _sources_context(wiki, results)
            elif do_search:
                context = ("The web search failed just now. Answer with what you know and add, in "
                           "one short sentence, that it may be outdated.")
        elif forced:
            notice = "Web search isn't set up, so here's what I already know. "
        if wants_current_info and not context:
            context = NO_SEARCH_CONTEXT  # without results, small models invent "today's" numbers

        attr = handler_input.attributes_manager.session_attributes
        history = attr.get("history", [])
        messages = history + [{"role": "user", "content": query}]
        remaining = ALEXA_DEADLINE_SECONDS - (time.monotonic() - started)
        if remaining >= MIN_LLM_TIMEOUT_SECONDS + LLM_RETRY_RESERVE_SECONDS:
            first_timeout = min(REQUEST_TIMEOUT_SECONDS, remaining - LLM_RETRY_RESERVE_SECONDS)
        else:
            first_timeout = max(MIN_LLM_TIMEOUT_SECONDS, min(REQUEST_TIMEOUT_SECONDS, remaining))
        ok, answer = _ask_llm(messages, context=context, timeout=first_timeout)
        remaining = ALEXA_DEADLINE_SECONDS - (time.monotonic() - started)
        if not ok and answer == LLM_TIMEOUT_SPEECH and remaining >= MIN_LLM_TIMEOUT_SECONDS:
            logger.info("First attempt timed out; retrying with %.1fs.", remaining)
            ok, answer = _ask_llm(messages, context=context, timeout=remaining)
        if ok:
            answer = notice + answer
            # Only successful exchanges go into the history, so errors don't pollute the context.
            history += [{"role": "user", "content": query}, {"role": "assistant", "content": answer}]
            attr["history"] = history[-MAX_HISTORY_MESSAGES:]

        return (handler_input.response_builder.speak(answer)
                .ask("Anything else? To finish, just say stop.").response)


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speak = ("Just talk to me naturally: ask a question, or ask for an idea, a poem or some "
                 "advice. What would you like to know?")
        return handler_input.response_builder.speak(speak).ask(speak).response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (is_intent_name("AMAZON.CancelIntent")(handler_input)
                or is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        return handler_input.response_builder.speak(random.choice(GOODBYES)).response


class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        speak = "Oops, I didn't get that. Could you say it again?"
        return handler_input.response_builder.speak(speak).ask(speak).response


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error("Unhandled exception: %s", exception, exc_info=True)
        speak = "Sorry, something went wrong on my side. Could you try again?"
        return handler_input.response_builder.speak(speak).ask(speak).response


sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(AskModelIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
