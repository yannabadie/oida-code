# Diagnostic CLI quickstart

This is the 10-minute front-door path for a Python reviewer who wants a
diagnostic second opinion on a local repo or diff.

It is diagnostic-only. It is not a merge decision, production-readiness
assessment, security certification, public benchmark result, or autonomous
repair plan.

## Install

From the `oida-code` checkout:

```powershell
python -m pip install -e ".[dev]"
```

## Run the deterministic diagnostic review

From `C:\Code\Unslop.ai`, replace `<target-repo>` with the Python repo you
want to inspect:

```powershell
python -m oida_code.cli audit <target-repo> --base HEAD --format markdown --out .oida\oida-diagnostic.md
```

For a JSON artifact that preserves the internal legacy schema:

```powershell
python -m oida_code.cli audit <target-repo> --base HEAD --format json --out .oida\oida-diagnostic.json
```

## Read the Markdown

The Markdown report starts with:

- a diagnostic-only banner;
- a claim-level diagnostic status;
- tool evidence;
- critical findings when tools report them;
- a human follow-up checklist when more inspection is needed.

The Markdown report deliberately does not expose the legacy internal JSON
verdict labels as product claims.

## What this does not prove

The report does not prove that a change is correct, safe to merge, production
ready, free of bugs, free of security defects, or valid across a benchmark.

The official OIDA fusion fields remain blocked in this product path. JSON keeps
legacy internal fields for compatibility, but the human Markdown is the
diagnostic reviewer surface.

## GitHub Action note

The reusable GitHub Action is the same diagnostic-only path packaged for CI.
Caller workflows should keep `permissions: contents: read` by default and grant
`security-events: write` only to the job that sets `upload-sarif: "true"`.
The action defaults remain conservative: `upload-sarif: "false"`,
`enable-tool-gateway: "false"`, and `fail-on: "none"`.
