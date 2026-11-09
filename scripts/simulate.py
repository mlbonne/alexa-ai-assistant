"""Talk to your live skill through Amazon's official simulator (needs the ASK CLI, configured).

    python scripts/simulate.py --skill-id amzn1.ask.skill.XXXX "open smart helper" "why is the sky blue"

The first utterance starts a new session; the rest continue it. For each one it prints the intent
Alexa matched, the captured slot text, how long the skill took, and what it said.
The skill ID can also come from .ask/ask-states.json (written when you set up the ASK CLI).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASK = shutil.which("ask")  # on Windows this finds ask.cmd, which works even if PowerShell blocks ask.ps1


def ask_json(*args):
    out = subprocess.run([ASK, "smapi", *args], capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        sys.exit("ASK CLI error:\n" + (out.stderr or out.stdout)[:800])


def skill_id_from_state():
    path = os.path.join(ROOT, ".ask", "ask-states.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)["profiles"]["default"]["skillId"]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("utterances", nargs="+")
    parser.add_argument("--skill-id", default=skill_id_from_state())
    parser.add_argument("--locale", default="en-US")
    args = parser.parse_args()
    if not ASK:
        sys.exit("ASK CLI not found. Install it: npm install -g ask-cli  (see docs/05-ask-cli.md)")
    if not args.skill_id:
        sys.exit("Pass --skill-id (Developer Console -> your skill -> 'Copy Skill ID').")

    for index, text in enumerate(args.utterances):
        mode = "FORCE_NEW_SESSION" if index == 0 else "DEFAULT"
        started = ask_json("simulate-skill", "-s", args.skill_id, "--input-content", text,
                           "--device-locale", args.locale, "--session-mode", mode)
        result = {}
        for _ in range(30):
            result = ask_json("get-skill-simulation", "-s", args.skill_id, "-i", started["id"])
            if result.get("status") != "IN_PROGRESS":
                break
            time.sleep(2)
        print("> " + text)
        res = result.get("result", {})
        if res.get("error"):
            print("  error: " + res["error"].get("message", "")[:200])
        for inv in (res.get("skillExecutionInfo") or {}).get("invocations", []):
            request = inv.get("invocationRequest", {}).get("body", {}).get("request", {})
            intent = request.get("intent") or {}
            slots = {k: v.get("value") for k, v in (intent.get("slots") or {}).items() if v.get("value")}
            speech = (inv.get("invocationResponse", {}).get("body", {}).get("response", {})
                      .get("outputSpeech") or {}).get("ssml", "")
            ms = (inv.get("metrics") or {}).get("skillExecutionTimeInMilliseconds")
            print("  intent=%s %s [%s ms]" % (intent.get("name", request.get("type")), slots, ms))
            print("  says: " + speech.replace("<speak>", "").replace("</speak>", ""))


if __name__ == "__main__":
    main()
