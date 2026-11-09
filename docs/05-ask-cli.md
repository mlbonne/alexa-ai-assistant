# 5. Use the ASK CLI (optional)

The **Alexa Skills Kit CLI** is Amazon's official command-line tool. Once it's set up, you can
deploy code, update the interaction model and test, all from the terminal. That makes changes
much faster, and lets coding agents help you within Amazon's rules.

## 5.1 Install

You need [Node.js](https://nodejs.org) and git.

```bash
npm install -g ask-cli
ask --version
```

**Windows / PowerShell:** if you get *"running scripts is disabled on this system"*, call
`ask.cmd` instead of `ask` (for example `ask.cmd configure`). This avoids PowerShell's script
policy without changing any security settings.

## 5.2 Sign in once

```bash
ask configure
```

1. Your browser opens **Login with Amazon**. Sign in with your developer account and allow access.
2. Back in the terminal, confirm that you signed in (`Y`).
3. When asked **"Do you want to link your AWS account?"**, answer **No**. Alexa-hosted skills
   don't need AWS.

Check that it works with your skill ID (Developer Console → your skill → **Copy Skill ID**):

```bash
ask smapi get-skill-status -s amzn1.ask.skill.YOUR-SKILL-ID
```

## 5.3 Get your skill's code repository

Every Alexa-hosted skill has a private git repository. Get its URL:

```bash
ask smapi get-alexa-hosted-skill-metadata -s amzn1.ask.skill.YOUR-SKILL-ID
```

To clone it, git needs the ASK CLI as its credential helper. **The helper only works inside a
folder with `ask-resources.json` and `.ask/ask-states.json`**, so create that folder first.

In a new folder, called `hosted-skill/` below:

1. Copy this repo's `ask-resources.json` into it.
2. Create `.ask/ask-states.json`:
   ```json
   {
     "askcliStatesVersion": "2020-03-31",
     "profiles": { "default": { "skillId": "amzn1.ask.skill.YOUR-SKILL-ID" } }
   }
   ```
3. Then run:
   ```bash
   git init
   git remote add origin https://git-codecommit.REGION.amazonaws.com/v1/repos/YOUR-REPO-ID
   git config credential.helper ""
   git config --add credential.helper "!ask util git-credentials-helper"   # Windows: ask.cmd
   git config credential.UseHttpPath true
   git fetch origin
   git checkout -f -B dev origin/dev
   ```

The repository has `dev`, `master` and `prod` branches. Code you saved in the console is already
committed there.

## 5.4 Deploy code

Copy `lambda/lambda_function.py` (and your `config.py`) into `hosted-skill/lambda/`, then:

```bash
git add lambda/
git commit -m "Update skill code"
git push origin dev
git push origin dev:master     # in our tests, the deploy was triggered by pushing master
```

Watch the deployment:

```bash
ask smapi get-skill-status -s amzn1.ask.skill.YOUR-SKILL-ID
```

Wait until `hostedSkillDeployment` shows `SUCCEEDED` with your new commit ID.

## 5.5 Update the interaction model

The hosted repository doesn't contain the interaction model, so push it directly:

```bash
ask smapi set-interaction-model -s amzn1.ask.skill.YOUR-SKILL-ID -l en-US \
  --interaction-model "file:skill-package/interactionModels/custom/en-US.json"
ask smapi get-skill-status -s amzn1.ask.skill.YOUR-SKILL-ID     # wait for interactionModel SUCCEEDED
```

If the build fails, the status shows why, and **the previous model stays live**.

## 5.6 Test from the terminal

```bash
python scripts/simulate.py --skill-id amzn1.ask.skill.YOUR-SKILL-ID \
  "open smart helper" "why is the sky blue" "tell me more"
```

For each line it prints the intent Alexa matched, the captured text, how long your code took,
and what it said. Testing must be enabled for the skill (step 6.1).

Next: [6. Test on your Echo](06-test-on-your-echo.md)
