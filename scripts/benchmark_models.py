"""Find a model that is fast enough for Alexa (~8 second limit, including search).

Reads LLM_API_KEY and LLM_BASE_URL from the environment or lambda/config.py. Never prints the key.

    pip install "openai>=1.30,<2"
    python scripts/benchmark_models.py --list                       # what the provider offers
    python scripts/benchmark_models.py model-a model-b model-c       # time them

A good model for voice: every answer under ~4 s, never empty, natural in your language.
Free endpoints can queue: run it more than once, at different times of day.
"""
import argparse
import ast
import os
import statistics
import sys
import time

try:
    import openai
    from openai import OpenAI
except ImportError:
    sys.exit('Install the client first: pip install "openai>=1.30,<2"')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PROMPTS = ["why is the sky blue", "write a four line poem about coffee",
                   "who invented the telephone"]
SYSTEM = ("You are a voice assistant. Answer in 2 to 4 short sentences, no markdown, no emojis, "
          "because the answer will be spoken aloud.")


def load_config():
    cfg = {}
    path = os.path.join(ROOT, "lambda", "config.py")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for node in ast.parse(f.read()).body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    cfg[node.targets[0].id] = node.value.value
    for name in ("LLM_API_KEY", "LLM_BASE_URL"):
        if os.environ.get(name):
            cfg[name] = os.environ[name]
    key = cfg.get("LLM_API_KEY", "")
    if not key or "paste-your" in key:
        sys.exit("No LLM_API_KEY found. Set it in lambda/config.py or as an environment variable.")
    return key, cfg.get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="*", help="model IDs to test")
    parser.add_argument("--list", action="store_true", help="list the provider's model IDs and exit")
    parser.add_argument("--prompt", action="append", help="custom prompt (repeatable)")
    parser.add_argument("--timeout", type=float, default=15, help="seconds before giving up (default 15)")
    parser.add_argument("--delay", type=float, default=1.6, help="pause between calls, for rate limits")
    args = parser.parse_args()

    key, base_url = load_config()
    client = OpenAI(api_key=key, base_url=base_url, timeout=args.timeout, max_retries=0)
    print("Provider:", base_url)

    if args.list or not args.models:
        ids = sorted(m.id for m in client.models.list())
        print("\n".join(ids))
        print("\n%d models. Pass some of them as arguments to time them." % len(ids))
        return

    prompts = args.prompt or DEFAULT_PROMPTS
    summary = []
    for model in args.models:
        print("\n=== " + model)
        extra = {"reasoning_effort": "none"}
        times, problems = [], 0
        for prompt in prompts:
            started = time.monotonic()
            try:
                try:
                    r = client.chat.completions.create(
                        model=model, max_tokens=400, extra_body=extra or None,
                        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
                except openai.BadRequestError:
                    extra = {}  # this model/provider doesn't accept reasoning_effort
                    r = client.chat.completions.create(
                        model=model, max_tokens=400,
                        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
                elapsed = time.monotonic() - started
                text = (r.choices[0].message.content or "").strip()
                details = r.usage.completion_tokens_details if r.usage else None
                reasoning = getattr(details, "reasoning_tokens", None) if details else None
                times.append(elapsed)
                if not text:
                    problems += 1
                print("  %5.1fs  finish=%-6s reasoning_tokens=%-4s | %s" % (
                    elapsed, r.choices[0].finish_reason, reasoning,
                    text.replace("\n", " / ")[:110] or "<EMPTY - likely spent its budget reasoning>"))
            except openai.APITimeoutError:
                problems += 1
                print("  TIMEOUT after %.0fs (too slow for Alexa)" % args.timeout)
            except openai.APIStatusError as exc:
                problems += 1
                print("  HTTP %s %s" % (exc.status_code, str(exc).replace(key, "***")[:110]))
            time.sleep(args.delay)
        worst = max(times) if times else None
        verdict = "GOOD" if times and not problems and worst < 4 else "OK-ish" if times and not problems and worst < 6 else "NO"
        summary.append((model, statistics.median(times) if times else None, worst, problems, verdict))

    print("\n%-45s %8s %8s %8s  %s" % ("model", "median", "worst", "problems", "verdict"))
    for model, median, worst, problems, verdict in summary:
        fmt = lambda v: "%.1fs" % v if v is not None else "-"
        print("%-45s %8s %8s %8d  %s" % (model, fmt(median), fmt(worst), problems, verdict))


if __name__ == "__main__":
    main()
