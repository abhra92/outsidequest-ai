# Agent instructions — OutsideQuest AI

## Project

Streamlit app turning free time into outdoor missions via a configurable hosted
inference API (default: OpenRouter + `google/gemma-4-26b-a4b-it:free`, Apache 2.0).
Hacktoberfest 2026 Week 1 DEV Challenge ("Touch Grass") submission.

Flat module layout, **absolute imports** (`from config import ...`, `import safety`).
Python 3.11+ (venv: `.venv`, Python 3.12.13).

## Commands

```powershell
& ".venv\Scripts\python.exe" -m pytest tests -q   # 54 tests, must stay green
& ".venv\Scripts\python.exe" -m ruff check .      # lint, must stay clean
streamlit run app.py                              # app on http://localhost:8501
```

## Invariants (do not break)

- **Honesty:** fallback missions must stay labeled "written by humans, not AI".
  No fabricated benchmarks, screenshots, or claims. Live generation IS verified
  (OpenRouter, `nvidia/nemotron-3.5-lightning:free`, 2026-10-10) — but a real API key
  may exist in `.env` locally: never print, log, or commit it. Default Gemma 4 free can
  hit transient upstream 429s; app must keep degrading honestly to fallback.
- **Safety gate:** every rendered mission passes `safety.check_mission`. Safety notes
  must mention traffic/road. Fallback missions must satisfy duration→step limits
  (`MAX_STEPS_BY_DURATION = {10: 4, 20: 6, 30: 8}`).
- **Security:** never hardcode/log/commit API keys; `.env` is gitignored; `.env.example`
  contains placeholders only. Model output is never rendered as HTML or executed.
- **Privacy:** SQLite history stores no location, no credentials (see `storage.py`).
- **Core generation** must go through a configurable OpenAI-compatible endpoint with
  an open-weight model — no closed-model API, no local model runtime, no Ollama.
- Tests construct `MissionContent` with ≥3 steps (Pydantic min length).
- Run pytest + ruff after any change; fix before finishing.
