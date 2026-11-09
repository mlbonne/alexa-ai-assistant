# 3. Create the skill

All of this happens in the **Alexa Developer Console**:
<https://developer.amazon.com/alexa/console/ask>. Screen labels may differ slightly over time.

> Amazon blocks AI agents and browser automation on the developer console. Do these steps
> yourself, or use the ASK CLI ([step 5](05-ask-cli.md)), which is Amazon's official tool for
> automating skill development.

## 3.1 Create it

1. Click **Create Skill**.
2. **Name:** anything (e.g. *Smart Helper*). **Primary locale:** **English (US)**.
   The locale must match your Echo's language setting. For another language, see
   [Customize → Language](08-customize.md#language).
3. **Experience:** *Other*. **Model:** **Custom**.
4. **Hosting:** **Alexa-hosted (Python)**. Amazon runs your code for free, so you don't need an
   AWS account.
5. **Hosting region:** the one closest to you (lower latency).
6. **Template:** *Start from Scratch*. Then **Create Skill**, and wait about a minute.

## 3.2 Paste the interaction model

The interaction model is the list of things users can say. It's in
[`skill-package/interactionModels/custom/en-US.json`](../skill-package/interactionModels/custom/en-US.json).

1. Left menu: **Interaction Model → JSON Editor**.
2. Select everything in the editor, delete it, and paste the whole file.
3. **Save**, then **Build skill**. Wait for *Build successful*.

The default invocation name is **"smart helper"**. To change it, edit `INVOCATION_NAME` in
`scripts/build_interaction_model.py` and run `python scripts/build_interaction_model.py`.
Invocation names must be lower case, two or more words, and can't contain "alexa".

## Why the interaction model looks the way it does

Alexa custom skills **never receive the raw text** of what you said. Every utterance has to
match a sample phrase of some intent, and that shapes the whole design:

- The free-text slot type, `AMAZON.SearchQuery`, **must have a fixed word before it**. A sample
  like `{query}` on its own is rejected. That's why there's one intent per leading word
  (`who {query}`, `what {query}`, `write {query}`...). Alexa strips the leading word from the
  slot, so the code puts it back ("who" + "invented the radio").
- To also allow **free-form sentences** with no leading word, `FreeTalkIntent` uses a
  **custom slot type** (`FreeText`). A custom slot type *can* stand alone (`{phrase}`), and
  custom slot values aren't limited to the listed examples. This is the well-known "catch-all"
  workaround. Long sentences may be recognized a little less accurately by voice than the
  intents with a leading word, which is why both kinds are kept.
- **Rules that made Alexa reject a build for us** (the build script checks all of these):
  - Intent names are compared **without regard to case**. `QuestionPorQue` and
    `QuestionPorque` collide.
  - A slot name can't have two different types. The catch-all slot is named `phrase`, not
    `query`.
  - The same sample phrase can't appear in two intents.

Next: [4. Add the code](04-add-the-code.md)
