# I Built an App That Turns Free Time Into Outdoor Missions (Hacktoberfest Week 1)

> **Draft — not yet published.** DEV.to submission draft for the Hacktoberfest 2026
> Week 1 DEV Challenge: ["Touch Grass"](https://dev.to/challenges/hacktoberfest-week1-2026-10-05).
> Tags: `#devchallenge`, `#hf26challenge`. AI disclosure: `some_ai` — see footer.

---

We've all been there: you finally have 20 free minutes, and 40 minutes later you're
still doomscrolling. **OutsideQuest AI** is my Hacktoberfest Week 1 ("Touch Grass")
build: tell it how much time you have, where you'll go, and how hard you want it to be,
and it hands you a small outdoor mission you can finish before your tea goes cold.

## What it does

1. You pick **time** (10/20/30 min), **place** (garden, neighborhood, park, trail...),
   **difficulty**, and optional **interests** (birds, clouds, plants, architecture...).
2. The app builds a structured prompt and sends it to an **open-weight model**
   (Gemma 4 26B A4B, Apache 2.0) through a configurable OpenAI-compatible endpoint —
   OpenRouter by default, Hugging Face's router, or any gateway you point it at.
3. The JSON response is parsed into **Pydantic models** and pushed through a
   **deterministic safety checker** (regex rules for trespassing, wildlife handling,
   road behavior, medical claims, HTML/JS markup).
4. You get a mission card: steps, an observation goal, a "done when" condition, and
   safety notes. Hit **Go outside mode** to hide every control, then mark it complete
   with a one-line reflection. History lives in local SQLite.

```mermaid
flowchart TD
    A[User inputs] --> B[Prompt builder]
    B --> C{API key configured?}
    C -- yes --> D[Hosted inference: Gemma 4 via OpenAI-compatible API]
    C -- no --> E[Curated fallback set, labeled "written by humans"]
    D --> F[Pydantic parse]
    F --> G[Safety gate]
    G -- fail --> E
    G -- pass --> H[Mission card]
    E --> H
    H --> I[Outside mode → complete → local history]
```

## The honesty design (my favorite part)

Most "AI generator" demos collapse into a sad error state when the API key is missing.
This app **degrades on purpose**:

- No key → you get a **curated fallback mission written by humans**, shown with an
  explicit *"written by humans, not AI"* badge and the exact reason for the fallback.
- Model returns garbage, unsafe content, or markup → same honest fallback path.
- The sidebar always states which provider/model is active and whether a key was found.

No key ships with the repo (obviously). When I first wired my key up, the default
Gemma 4 free endpoint answered with a transient upstream 429 from OpenRouter's Google
pool — so the app calmly showed the fallback mission *with the exact error reason*.
One `OUTSIDEQUEST_MODEL` switch later (to `nvidia/nemotron-3.5-lightning:free`, open
weights under the OpenMDW-1.1 license, plus a bigger token budget for its reasoning
style), the same app generated a real AI mission, passed the safety gate, and saved it
to history labeled `ai`. That's the demo: **degradation is a feature, not an error state.**

## Safety: rules first, model second

The model is not the safety system. Every mission — model-generated or curated — must
pass `safety.check_mission()`:

- **Trespass / restricted areas**, fence-climbing, abandoned buildings
- **Wildlife**: approach, feed, handle (with negation awareness — "never handle
  unknown insects" passes, "feed the fox" fails)
- **Road & railway** behavior; every mission's safety notes must mention traffic context
- **Medical claims**: "treats your anxiety" → rejected
- **No HTML/JS** anywhere — model text is always rendered as plain text

Fallback missions also have to respect duration limits (10 min → max 4 steps, etc.),
so a 10-minute quest never ambushes you with seven steps.

## Stack

- **Streamlit** (UI, outside mode, print-friendly mission card)
- **Pydantic v2** (strict mission schema)
- **Requests** (chat completions with retry/backoff, mapped error taxonomy:
  401 auth, 429 rate limit, 5xx server, timeout)
- **SQLite** (local history — no location columns, no credentials, ever)
- **pytest** (54 tests) + **ruff** (lint)

```
app.py → mission_engine.py → providers/ (openai_compatible | huggingface)
                ↓
        models.py (Pydantic) → safety.py → storage.py (SQLite)
```

## Run it

```powershell
git clone <repo-url>
cd outsidequest-ai
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # paste your OPENROUTER_API_KEY (or skip — fallback works)
streamlit run app.py
```

Tests: `pytest -q` → 54 passed. Lint: `ruff check .` → clean.

## What I'd add next

- Streaks + badges (gently gamified, still offline-friendly)
- Export history as Markdown
- More fallback missions per place type
- Optional weather API (still no GPS — you type the place)

## Honest limitations

- Free endpoints are rate-limited: OpenRouter's upstream pools (Google AI Studio for
  Gemma) returned transient 429s during testing; the fallback path covers it.
- Safety checking is regex-based: a guardrail, not a guarantee.
- OpenRouter's free tier rate-limits (~50 requests/day without credits).

---

**Tags:** `#devchallenge` `#hf26challenge`

**AI disclosure:** drafted with AI assistance (`some_ai`); all code, tests, safety rules,
fallback missions, and screenshots are part of this repository — read them and judge
for yourself.
