# Contributing

Thanks for helping. Good first contributions: a new job source, a new country, better language detection, or support for another assistant.

## Setup

```bash
git clone https://github.com/dheerajkarwasra/jobpilot.git && cd jobpilot
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,gsheets]"
pytest
```

## Rules

- Tests run offline. Record a small real response as a fixture in `tests/fixtures/` and serve it with `FakeHttp`
- No personal data anywhere in the repo. Use made up names like Alex Example
- A failing source must never stop a run. Raise `SourceError` with a clear message
- Never add code that sends, deletes or changes mail
- Keep generated text plain: no em dashes, no buzzwords

## Adding a source

1. `src/jobpilot/sources/<name>.py` with `fetch(ctx) -> List[Job]`. Set `posting_ref` with a short prefix (for example `AN-`) when the source has an ID
2. Register it in `sources/__init__.py` and add a switch in `search.enabled_sources`
3. Add a fixture and a test in `tests/test_sources.py`
4. Document it in `docs/SOURCES.md`

## Adding an assistant target

Add it to `TARGETS` in `adapters.py`, write the files in `install()`, add a test in `tests/test_setup_and_adapters.py`, and document it in `docs/ASSISTANTS.md`.
