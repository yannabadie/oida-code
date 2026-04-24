# oida-code

**AI code verifier.** Measures the gap between what AI-written code appears to do and what it actually guarantees.

Built on the OIDA v4.2 formal model of operational debt and corrupt success (Abadie, 2026).

## Status

Phase 1 bootstrap — CLI skeleton with `inspect`, Pydantic I/O models, and vendored deterministic scorer. Not production-ready; see `memory-bank/progress.md`.

## Install (dev)

```bash
python -m pip install -e ".[dev]"
```

## Quickstart

```bash
oida-code inspect ./path/to/repo --base HEAD --out .oida/request.json
```

## License

MIT — see `LICENSE`.
