# VibeCoding Implementation Backlog

本文档把 ChangePlatAutoNext 拆成适合逐步交给 AI 或开发者完成的小任务。每个任务都有范围、输入、输出和验收标准。

## Epic 0: Project Hygiene

### T0.1 Add repository metadata and GPL license

Status: done in scaffold.

Files:

- `.gitignore`
- `README.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `LICENSE`
- `.github/workflows/ci.yml`

Acceptance:

- `find . -maxdepth 2 -type f` shows standard GitHub project files.
- Generated files are covered by `.gitignore`.
- Project metadata declares `GPL-3.0-only` because of PyQt6.

### T0.2 Configure test tooling

Files:

- `pyproject.toml`
- `requirements/dev.txt`
- `Makefile`
- `tests/`

Acceptance:

```bash
python -m pip install -r requirements/dev.txt
make test
```

Expected initial result may be zero tests until task-specific tests are added.

### T0.3 Add one-command install and packaging script

Files:

- `install.py`
- `requirements/build.txt`
- `src/change_plate_next/interfaces/desktop/app.py`
- `packaging/pyinstaller_entry.py`
- `docs/user/install_and_build.md`

Acceptance:

- `python install.py --skip-build` creates `.venv` and installs dependencies.
- `python install.py` runs PyInstaller for the current platform.
- Build output appears in `dist/`.
- The packaged app can launch the PyQt6/QSS scaffold window.

## Epic 1: Domain Core

### T1.1 Finalize domain models

Files:

- `src/change_plate_next/domain/models.py`
- `tests/unit/test_domain_models.py`

Implement:

- Immutable IDs for plate, local filament, AMS channel.
- `FilamentSignature.normalized()`.
- Queue copy normalization helper.
- Export summary value object.

Acceptance:

```bash
python -m pytest tests/unit/test_domain_models.py
```

### T1.2 Implement channel mapping service

Files:

- `src/change_plate_next/domain/channel_mapping.py`
- `tests/unit/test_channel_mapping.py`
- `docs/api/channel_mapping_contract.md`

Implement:

- Auto assign by `color + material + nozzle_diameter`.
- Reset to local channels.
- Validate conflicts.
- Aggregate filament usage by actual channel.
- Channel limit validation.

Acceptance:

- Same color/material/nozzle maps to same channel.
- Different color maps to different channel.
- Same channel with conflicting signatures raises `ChannelMappingError`.
- Copies multiply usage.

### T1.3 Define safety policies

Files:

- `src/change_plate_next/domain/policies.py`
- `tests/unit/test_policies.py`

Implement:

- `ArchiveSafetyPolicy` defaults.
- `GcodeSafetyPolicy` defaults.
- `InsertionStrategy` enum.
- `MachineProfile` for A1 defaults.

Acceptance:

- Defaults match architecture document.
- Risky insertion strategy is not default.

## Epic 2: G-code Pipeline

### T2.1 Implement legacy crypto

Files:

- `src/change_plate_next/adapters/gcode/legacy_crypto.py`
- `tests/unit/test_legacy_crypto.py`

Implement:

- XOR bytes.
- Base64 encrypt/decrypt.
- BOM stripping.
- Read legacy `code.rar`.

Acceptance:

- Roundtrip text passes.
- BOM input passes.
- Empty key raises error.

### T2.2 Implement lightweight G-code command parser

Files:

- `src/change_plate_next/adapters/gcode/parser.py`
- `tests/unit/test_gcode_parser.py`

Implement:

- Classify blank/comment/command lines.
- Parse `M620` and `M621` S tool number.
- Parse standalone `Tn`.
- Preserve prefix, suffix, comments.

Acceptance:

- `; M620 S0A` remains comment.
- `M620 S0A ; switch` parses tool 0.
- `M621 S1 A` parses tool 1.
- `T255` parses as reserved tool but is recognized.

### T2.3 Implement channel remap stage

Files:

- `src/change_plate_next/adapters/gcode/stages.py`
- `tests/unit/test_gcode_channel_remap.py`

Implement:

- Rewrite `M620`, `M621`, and `Tn` using local-id to AMS-channel mapping.
- Skip reserved tool numbers 255 and 1000.
- Skip comments and unknown commands.

Acceptance:

- Existing old-project tests pass when ported.
- Output preserves comments and line count.

### T2.4 Implement plate-change insertion stage

Files:

- `src/change_plate_next/adapters/gcode/stages.py`
- `tests/unit/test_gcode_insertion.py`

Implement:

- Finish sound marker detection.
- Insert before finish sound block.
- Append only when strategy explicitly allows it.
- Idempotence when marker already exists.

Acceptance:

- Two marker happy path inserts before first marker of final block.
- Missing marker raises by default.
- Append strategy returns warning.

### T2.5 Implement GcodePipeline

Files:

- `src/change_plate_next/adapters/gcode/pipeline.py`
- `tests/unit/test_gcode_pipeline.py`

Implement:

- Stage ordering.
- Warning aggregation.
- Metrics aggregation.
- Segment context.

Acceptance:

- Pipeline can apply start patch, remap, M73, insertion in order.
- Warnings include stage names.

## Epic 3: 3MF Package Adapter

### T3.1 Implement ArchiveGuard

Files:

- `src/change_plate_next/adapters/bambu_3mf/archive_guard.py`
- `tests/unit/test_archive_guard.py`

Implement:

- CRC check.
- File count limit.
- Total uncompressed size limit.
- Single file size limit.
- Compression ratio limit.
- Path safety resolver.
- Symlink rejection.

Acceptance:

- Path traversal fixture is rejected.
- Backslash path fixture is rejected.
- Normal zip fixture extracts.

### T3.2 Implement SafeXmlStore

Files:

- `src/change_plate_next/adapters/bambu_3mf/safe_xml.py`
- `tests/unit/test_safe_xml.py`

Implement:

- Parse file with max byte limit.
- Use `defusedxml` when available.
- Reject DOCTYPE/ENTITY fallback input.
- Write XML consistently.

Acceptance:

- No code path uses undefined `ET`.
- XXE-like fixture is rejected.

### T3.3 Implement MetadataReader

Files:

- `src/change_plate_next/adapters/bambu_3mf/metadata_reader.py`
- `tests/unit/test_metadata_reader.py`
- `tests/fixtures/3mf/fixture_builder.py`

Implement:

- Parse `slice_info.config`.
- Parse `model_settings.config` path overrides.
- Resolve plate assets.
- Detect unsliced 3MF.
- Return domain `Plate` objects.

Acceptance:

- Multi-plate synthetic package returns all plates.
- Missing `plate_N.gcode` gives actionable error.

### T3.4 Implement MetadataRewriter

Files:

- `src/change_plate_next/adapters/bambu_3mf/metadata_rewriter.py`
- `tests/unit/test_metadata_rewriter.py`

Implement:

- Rewrite `slice_info.config` target plate.
- Rewrite `model_settings.config` target gcode file.
- Rewrite `_rels/.rels` target references.
- Rewrite `filament_sequence.json`.

Acceptance:

- Ported old failing test passes.
- XML files remain parseable.

### T3.5 Implement PackageWriter

Files:

- `src/change_plate_next/adapters/bambu_3mf/package_writer.py`
- `tests/integration/test_package_writer.py`

Implement:

- Staging copy.
- Merged G-code write.
- MD5 write.
- Preview composer call.
- Metadata rewriter call.
- Zip output.

Acceptance:

- Output 3MF contains target G-code and MD5.
- Non-target G-code is removed or handled according to plan.

## Epic 4: Application Workflow

### T4.1 Implement MergePlanner

Files:

- `src/change_plate_next/application/merge_planner.py`
- `tests/unit/test_merge_planner.py`

Implement:

- Queue validation.
- Total copies calculation.
- Segment plan creation.
- Aggregated filament plan.
- Warning collection.

Acceptance:

- Empty queue fails.
- Zero total copies fails.
- Valid queue produces deterministic segment order.

### T4.2 Implement ExportOrchestrator

Files:

- `src/change_plate_next/application/export_orchestrator.py`
- `tests/integration/test_export_orchestrator.py`

Implement:

- Compile plan.
- Execute package writer.
- Return export summary.
- Emit progress events.

Acceptance:

- Synthetic two-plate export passes end-to-end.
- Progress events include plan, transform, metadata, pack.

## Epic 5: Interfaces

### T5.0 Implement theme infrastructure

Files:

- `src/change_plate_next/interfaces/desktop/theme.py`
- `src/change_plate_next/interfaces/desktop/styles/workshop_light.qss`
- `tests/unit/test_desktop_theme.py`
- `docs/user/modern_ui_design.md`

Acceptance:

- `load_qss("workshop_light")` returns bundled QSS.
- QSS contains primary button, status badge, table, editor, and progress styles.
- No business logic uses inline styles for static states.


### T5.0a Add desktop internationalization

Files:

- `src/change_plate_next/interfaces/desktop/i18n.py`
- `src/change_plate_next/interfaces/desktop/app.py`
- `tests/unit/test_i18n.py`

Acceptance:

- English, French, and Chinese strings are available.
- Startup language defaults from system locale.
- Unsupported locale falls back to English.
- UI shell has no hard-coded user-facing strings except product name and license.

### T5.1 Implement CLI inspect

Files:

- `src/change_plate_next/interfaces/cli/main.py`
- `tests/integration/test_cli_inspect.py`

Acceptance:

```bash
change-plate-next inspect tests/fixtures/3mf/basic.3mf --json
```

Outputs plate list and filament summary.

### T5.2 Implement CLI merge

Files:

- `src/change_plate_next/interfaces/cli/main.py`
- `tests/integration/test_cli_merge.py`

Acceptance:

```bash
change-plate-next merge --queue examples/queue.example.json
```

Produces an output 3MF with expected metadata.

### T5.3 Implement desktop ViewModels

Files:

- `src/change_plate_next/interfaces/desktop/view_models.py`
- `tests/unit/test_view_models.py`

Acceptance:

- Import result updates queue model.
- Channel conflict disables export state.
- Export warnings are display-ready.

### T5.4 Implement PyQt6 desktop UI

Files:

- `src/change_plate_next/interfaces/desktop/`

Acceptance:

- App opens.
- User can import synthetic 3MF.
- User can edit copies and channel mapping.
- Export runs on background worker.

## Epic 6: External Integration

### T6.1 Implement Bambu Connect launcher

Files:

- `src/change_plate_next/adapters/connect/bambu_connect_launcher.py`
- `tests/unit/test_bambu_connect_launcher.py`

Acceptance:

- URL encodes path, name, version.
- Launch uses injectable opener for tests.
