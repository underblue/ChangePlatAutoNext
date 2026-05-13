# ChangePlatAutoNext

ChangePlatAutoNext is a clean-architecture redesign of ChangePlatAuto, a Bambu sliced-3MF post-processor for automatic plate-change workflows.

The tool is designed to import already-sliced Bambu 3MF packages, compose their plate G-code into one output 3MF, remap filament channels, insert automatic plate-change G-code, update package metadata, and optionally hand the result to Bambu Connect.

## Status

This directory now contains a usable 1.0 desktop and CLI application for sliced 3MF inspection, single-output 3MF composition, G-code transformation, merged 3MF export, Bambu Connect handoff, PyQt6/QSS packaging, and automated tests.

## Supported Input

The software is intended for Bambu/Orca sliced 3MF packages that contain:

- `Metadata/slice_info.config`
- `Metadata/plate_N.gcode`
- plate metadata and preview assets

It does not slice models. If a 3MF contains only models, previews, and project settings but no `plate_N.gcode`, the user must slice it in Bambu Studio or Orca Slicer first.

## Current Implementation Status

Implemented:

- Domain models and channel mapping validation.
- G-code parser, remap stages, M73 plate-number encoding, start-position patch, plate hooks, cooling/wait/sound behavior, and safe plate-change insertion.
- Legacy XOR + Base64 snippet compatibility.
- Safe 3MF archive extraction.
- Safe XML parsing wrapper.
- Bambu 3MF metadata reader and rewriter.
- Merged 3MF writer with MD5 updates and preview fallback.
- CLI `inspect` and `merge`.
- PyQt6 + QSS desktop shell and PyInstaller entry.
- Multi-language desktop shell with English, French, and Chinese; defaults to system locale.
- Unit and integration tests with synthetic 3MF fixtures.

External release validation:

- Expand fixture coverage with more real-world 3MF metadata variants.
- Perform final real-printer validation with representative sliced 3MF files before public release.

## Core Capabilities

- Inspect sliced 3MF files safely.
- Extract plate metadata, prediction time, weight, preview images, and filament usage.
- Compose plates from one or more source packages into one output 3MF.
- Adjust print order by reordering imported plate rows.
- Set copies per imported plate instead of globally.
- Assign local filament IDs to actual AMS channels.
- Detect channel conflicts before export.
- Transform G-code through explicit pipeline stages.
- Insert configurable automatic plate-change G-code.
- Add optional G-code before and after every plate segment.
- Optionally cool the bed before unloading, wait before the next plate, and play repeated sound prompts during the wait.
- Optionally encode the current plate number into the M73 remaining-time field for display.
- Update derived 3MF metadata and MD5 files.
- Export a merged 3MF.
- Open the output through Bambu Connect URL handoff.

## Repository Layout

```text
ChangePlatAutoNext/
  .github/workflows/        CI definitions
  docs/                     Architecture, VibeCoding, ADR, user docs
  examples/                 Example input/config files
  requirements/             Dependency groups
  resources/                Repository-level default resource drafts
  scripts/                  Repository maintenance scripts
  src/change_plate_next/    Python package source
  tests/                    Unit, integration, and fixture tests
  pyproject.toml            Package metadata and tooling config
  README.md                 Project overview
```

## Architecture Summary

The project uses a `src/` layout and clean architecture boundaries:

```text
interfaces -> application -> domain
    |             |           ^
    v             v           |
 adapters ->    ports --------+
```

- `domain`: business objects and safety policies.
- `application`: use cases, merge planning, export orchestration.
- `ports`: protocols for package IO, settings, file system, and external launchers.
- `adapters`: concrete ZIP/XML/G-code/Bambu Connect implementations.
- `interfaces`: CLI and desktop UI.

See `docs/software_architecture_design.md` for the full design.


## One-Command Build

After cloning the project, users can install dependencies and build a local executable for their current operating system:

```bash
cd ChangePlatAutoNext
python install.py
```

The script creates `.venv`, installs runtime/desktop/image/build dependencies, and runs PyInstaller. Build output is written to `dist/`. See `docs/user/install_and_build.md` for platform notes and troubleshooting.

## Local Development

```bash
cd ChangePlatAutoNext
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,image,desktop]'
```

Run checks:

```bash
make test
make lint
make typecheck
```

Run the CLI:

```bash
python -m change_plate_next.interfaces.cli.main
```

## Safety Boundary

G-code can move hardware. The default behavior must remain conservative:

- Reject uncertain 3MF archive paths.
- Reject unsafe XML features.
- Do not rewrite unknown G-code commands.
- Do not insert plate-change G-code when the safe insertion marker cannot be found, unless the user explicitly selects a risky strategy.
- Do not directly start a printer job or store Bambu credentials.


## License

ChangePlatAutoNext is licensed under `GPL-3.0-only`. This is intentional because the desktop application uses PyQt6, whose open-source distribution is GPL v3. Proprietary closed-source distribution requires appropriate commercial licensing for PyQt6 and a full dependency license review. See `docs/license_policy.md`.

## Important Documents

- `docs/current_project_understanding.md`: reverse-engineered behavior of the existing project.
- `docs/software_architecture_design.md`: complete architecture design.
- `docs/vibecoding/agent_playbook.md`: instructions for AI-assisted implementation.
- `docs/vibecoding/implementation_backlog.md`: task-by-task implementation plan.
- `docs/api/module_contracts.md`: module responsibilities and contracts.
- `docs/user/workflows.md`: intended user workflows.
- `docs/user/install_and_build.md`: clone-to-executable installation and PyInstaller build guide.
- `docs/user/modern_ui_design.md`: PyQt6 + QSS desktop UI design.
- `docs/license_policy.md`: GPL/PyQt6 licensing policy.
