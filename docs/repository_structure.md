# Repository Structure

本文档定义 ChangePlatAutoNext 的 GitHub 仓库形态。它不是临时脚手架目录，而应按可持续维护的开源/内部项目标准组织。

## 1. Top-Level Layout

```text
ChangePlatAutoNext/
  .github/
    workflows/
      ci.yml
  docs/
    adr/
    api/
    user/
    vibecoding/
    current_project_understanding.md
    migration_plan.md
    repository_structure.md
    software_architecture_design.md
    license_policy.md
  examples/
    queue.example.json
  requirements/
    runtime.txt
    desktop.txt
    dev.txt
  resources/
  scripts/
    README.md
  src/
    change_plate_next/
  tests/
    unit/
    integration/
    fixtures/
  .gitignore
  CHANGELOG.md
  CONTRIBUTING.md
  LICENSE
  Makefile
  README.md
  pyproject.toml
```

## 2. Why `src/` Layout

The project uses `src/change_plate_next` instead of placing the package at repository root.

Reasons:

1. Tests import the installed package, not accidental local modules.
2. Packaging behavior is closer to real user installation.
3. It prevents shadowing issues when running commands from repo root.

## 3. Documentation Layout

| Path | Purpose |
| --- | --- |
| `docs/adr/` | Architecture decision records |
| `docs/api/` | Module contracts and behavior contracts |
| `docs/user/` | User-facing workflows, modern PyQt6/QSS UI design, and future manuals |
| `docs/vibecoding/` | AI-assisted implementation instructions |
| `docs/current_project_understanding.md` | Reverse-engineered old project behavior |
| `docs/software_architecture_design.md` | Main architecture document |
| `docs/migration_plan.md` | Migration from current implementation |

## 4. Source Layout

```text
src/change_plate_next/
  domain/
  application/
  ports/
  adapters/
    bambu_3mf/
    gcode/
    connect/
  interfaces/
    cli/
    desktop/
  resources/
```

Rules:

- Domain must stay pure.
- Application depends on ports, not adapters.
- Adapters implement ports.
- Interfaces compose adapters and application services.

## 5. Test Layout

```text
tests/
  unit/
    test_channel_mapping.py
    test_gcode_parser.py
  integration/
    test_export_synthetic_3mf.py
  fixtures/
    gcode/
    3mf/
```

Rules:

- Unit tests must be fast and avoid real package IO unless testing adapter safety.
- Integration tests can build synthetic 3MF files in temp directories.
- Fixtures must be small and safe to publish.
- Private 3MF files belong outside the repository.

## 6. Requirements Layout

| File | Purpose |
| --- | --- |
| `requirements/runtime.txt` | Minimal runtime dependencies |
| `requirements/desktop.txt` | GUI/image optional dependencies |
| `requirements/dev.txt` | Editable install plus test/lint/type tools |

`pyproject.toml` remains the primary packaging definition. Requirements files are convenience entrypoints for users and CI.

## 7. Generated Files Policy

Do not commit:

- `__pycache__/`
- `.DS_Store`
- `.pytest_cache/`
- `.venv/`
- build outputs
- exported 3MF files
- private sample files
- old release binaries

These are covered by `.gitignore`.

## 8. Large Fixture Policy

Use synthetic fixtures whenever possible. If real-world 3MF samples are needed:

1. Store them outside git.
2. Document their expected structure.
3. Use a script to generate minimal public fixtures.
4. Never include customer/private model files.
