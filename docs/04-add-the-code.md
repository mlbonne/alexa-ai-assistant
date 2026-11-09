# 4. Add the code (console only)

This is the click-only path. If you prefer the terminal, use the [ASK CLI](05-ask-cli.md) instead.

Open your skill and click the **Code** tab. You'll see a `lambda` folder.

## 4.1 The skill code

1. Open `lambda_function.py`, select everything, delete it, and paste
   [`lambda/lambda_function.py`](../lambda/lambda_function.py). Click **Save**.
2. Open `requirements.txt`, replace its contents with
   [`lambda/requirements.txt`](../lambda/requirements.txt), and click **Save**:
   ```
   ask-sdk-core>=1.19.0
   openai>=1.30.0,<2.0.0
   ```

## 4.2 Your keys: config.py

**Alexa-hosted skills have no environment-variable settings** in the console, so the skill reads
its settings from a file next to the code.

1. Right-click the `lambda` folder → **Create File** → name it `lambda/config.py`.
2. Paste [`lambda/config.example.py`](../lambda/config.example.py) and fill in:
   - `LLM_API_KEY`: your LLM key;
   - `LLM_BASE_URL` and `LLM_MODEL`: your provider and the model you picked in [step 2](02-choose-a-fast-model.md);
   - `SEARCH_API_KEY`: your Tavily key (or leave the placeholder to run without search);
   - `TIMEZONE` / `UTC_OFFSET_HOURS`: so the assistant knows today's date.
3. Click **Save**.

Any value that still contains `paste-your` is treated as empty, so leftovers from the example
file can't break anything.

## 4.3 Deploy

Click **Deploy** (top right of the Code tab). The first deploy takes longer because it
installs the `openai` package.

> If you also edit `config.py` in a local copy (for example with Notepad), **close and reopen
> the file before editing**. Saving an old copy that was still open can silently put back
> values you already changed.

Next: [6. Test on your Echo](06-test-on-your-echo.md) (or [5. ASK CLI](05-ask-cli.md) first)
