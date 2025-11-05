# RayFlow

Visual flow editor with Ray distributed execution.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Start development server
rayflow dev

# Run a flow
rayflow run miflujo.json --input '{"key": "value"}'

# Run as API server
rayflow run miflujo.json --port 8090
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/
```

## Publishing to PyPI

This project uses GitHub Actions for automated publishing:

1. Create a new release on GitHub with a tag (e.g., `v0.1.0`)
2. GitHub Actions will:
   - Run tests on Python 3.10, 3.11, and 3.12
   - If tests pass, build the package
   - Publish to PyPI automatically

**Required Secret:**
- Add `PYPI_TOKEN` to GitHub Secrets (Settings → Secrets → Actions)
- Use your PyPI API token as the value

## License

RayFlow is licensed under the Business Source License 1.1.

- **Non-commercial use:** Free and unlimited
- **Commercial use:** Requires a commercial license
- **Change Date:** 2029-01-01 (converts to Apache 2.0)

For commercial licensing, contact: https://github.com/alejoair/rayflow

See [LICENSE](LICENSE) for full details.
