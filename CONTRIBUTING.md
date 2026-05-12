# Contributing

## Development Principles

- Keep domain logic independent from GUI, file system, ZIP, XML, and external applications.
- Prefer small, testable modules over large orchestration functions.
- Add tests before or alongside behavior changes.
- Do not commit virtual environments, release binaries, private 3MF files, or generated caches.
- Treat G-code transforms as safety-sensitive. Default to fail-fast behavior when an insertion point is uncertain.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,image,desktop]'
```

## Common Commands

```bash
make test
make lint
make typecheck
```

## Pull Request Checklist

- The change has a focused purpose.
- Unit tests cover the changed behavior.
- Integration tests cover changed 3MF package behavior when relevant.
- Documentation is updated when behavior, commands, or architecture changes.
- Generated files are not included.
