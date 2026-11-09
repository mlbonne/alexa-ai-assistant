# 6. Test on your Echo

## 6.1 Enable testing

Developer Console → your skill → **Test** tab → switch *Skill testing is enabled in* from
**Off** to **Development**.

## 6.2 Try the simulator first

Type, or hold the mic and speak:

```
open smart helper
why is the sky blue
tell me more
who is the current president of the united states
search for the tallest building in the world
stop
```

The **JSON Input / Output** panels show exactly what Alexa sent to your code and what it
returned, which is very useful for debugging.

## 6.3 On the device

No publishing is needed. A development skill is available on every Echo signed in to **the
same Amazon account** as your developer account.

1. In the Alexa app: **Devices → your Echo → Language**. Make sure it matches the skill's
   locale (English (US) for this repo). This is the most common reason the skill "isn't found".
2. Say **"Alexa, open smart helper"**, or ask in one go: **"Alexa, ask smart helper who
   invented the radio"**.

## How to talk to it

- After each answer the Echo **keeps listening for a few seconds** (blue light). Just speak.
  **Don't say "Alexa"** first: that leaves the skill and sends your words to regular Alexa.
- Ask follow-ups naturally ("tell me more", "and why is that?"). The conversation is
  remembered until the skill closes.
- Say **"stop"** to leave the skill.

## Spoken errors

When something fails, the skill **says what went wrong** instead of Alexa's generic error. For
example: *"Authentication error: the API key was rejected"*, *"The model took too long to
answer"*, or *"Your AI provider account is out of credit."* See
[Troubleshooting](09-troubleshooting.md) for each one.

## Logs

Code tab → **CloudWatch Logs** (top). Pick your hosting region and open the latest log stream.
The skill logs how long each model call and search took.

Next: [7. Web search](07-web-search.md)
