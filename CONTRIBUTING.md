# Contributing

This repo is the public contract surface for Bosun PKM. Changes here affect every fleet engine that validates notes, events, or JSON-RPC frames.

## Prerequisites

- Python 3.10+ (CI also runs 3.11 and 3.12)
- `pip`

```bash
python -m pip install ".[dev]"
```

Dev extras (`pyproject.toml`): `jsonschema`, `pytest`, `pyyaml`.

## Tests

```bash
python -m pytest tests/ -v
```

Schema-only smoke:

```bash
python tests/test_schemas.py
```

Keep fixtures UTF-8. vCard/iCalendar samples under `fixtures/codecs/` must use CRLF and 75-octet folding. Kindle clippings keep a UTF-8 BOM.

## Branch and pull requests

- Use conventional commits (`feat:`, `fix:`, `docs:`, `spec:`, `test:`, `chore:`).
- Open an issue before a breaking schema or RFC change.
- Prefer additive optional fields over required-field changes.
- Do not invent a CLA; none exists.

## Reporting issues

Use [GitHub Issues](https://github.com/Bosun-PKM-Tools/bosun-spec/issues). Include the schema path, a failing fixture, and the validator error when possible.

## License

Contributions are accepted under **MIT OR Apache-2.0**. See [LICENSE](LICENSE).
