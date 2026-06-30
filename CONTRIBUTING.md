# Contributing to Rayflow

Thanks for your interest in improving Rayflow! Contributions of all kinds are
welcome — bug reports, ideas, documentation, and code.

## License and the CLA

Rayflow is **dual-licensed**: AGPL-3.0-or-later for open use, plus a separate
commercial license (see [`COMMERCIAL-LICENSE.md`](COMMERCIAL-LICENSE.md)).

Because of this, code contributions require a **Contributor License Agreement**
([`CLA.md`](CLA.md)). You keep the copyright to your work; the CLA simply grants
the maintainer the right to include your contribution in both the AGPL and the
commercial editions. This is what keeps the dual-license model possible.

You do **not** need to do anything in advance: when you open your first pull
request, an automated check will ask you to confirm you agree to the CLA by
leaving a short comment. It only has to be done once.

If you prefer not to sign the CLA, you can still help via issues, feature
requests, and bug reports — those don't require it.

## Development setup

```bash
pip install -e ".[dev]"
pytest tests/
```

The visual editor frontend (React + Vite) lives in `rayflow/editor/frontend/`:

```bash
cd rayflow/editor/frontend
npm install
npm run build      # production build
npm run dev        # dev server on port 5173
npx tsc --noEmit   # type-check without emitting
```

## Pull request guidelines

- Keep changes focused; one logical change per PR.
- Add or update tests for behavior changes (`pytest tests/`).
- Match the style of the surrounding code.
- Make sure the test suite passes before requesting review.

## Reporting bugs

Open an issue with: what you expected, what happened, and the smallest steps or
flow JSON that reproduce the problem.
