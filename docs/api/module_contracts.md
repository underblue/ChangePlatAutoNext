# Module Contracts

本文档定义 ChangePlatAutoNext 各模块的职责边界、允许依赖、禁止行为和测试责任。后续 VibeCoding 任务应以此作为代码审查基准。

## 1. Dependency Rule

允许依赖方向：

```text
interfaces -> application -> domain
interfaces -> ports
application -> ports
adapters -> ports
adapters -> domain
```

禁止依赖方向：

```text
domain -> application
domain -> adapters
domain -> interfaces
application -> adapters
application -> interfaces
adapters -> interfaces
```

例外：composition root 可以把 adapter 注入 application，但 composition root 应位于 CLI 或 desktop app 启动层。

## 2. `domain/`

### Responsibility

`domain` 定义业务对象和不依赖 IO 的规则：

- plate、filament、queue、recipe、export summary。
- channel mapping 规则。
- safety policy 数据结构。
- 领域错误。

### Allowed Dependencies

- Python standard library。
- `typing`、`dataclasses`、`enum`。

### Forbidden

- `PyQt6`。
- `zipfile` 解包行为。
- XML 解析。
- 文件复制。
- `webbrowser`。
- 真实系统路径扫描。

### Public Contracts

Expected modules:

- `models.py`
- `errors.py`
- `channel_mapping.py`
- `policies.py`

Expected functions/classes:

```python
def auto_assign_channels(queue: list[QueueEntry], max_channels: int) -> ChannelAssignmentResult: ...
def validate_channel_assignments(queue: list[QueueEntry]) -> ValidationResult: ...
def aggregate_filament_usage(queue: list[QueueEntry]) -> tuple[AggregatedFilament, ...]: ...
```

### Test Responsibility

- No mocks required.
- Pure unit tests only.
- Every branch of conflict validation should be covered.

## 3. `application/`

### Responsibility

`application` 编排 use cases，但不接触具体技术实现。

- Inspect package use case。
- Build queue use case。
- Compile merge plan。
- Export orchestration。
- Settings application service。
- Progress events。

### Allowed Dependencies

- `domain`。
- `ports` protocols。
- Python standard library。

### Forbidden

- Direct `zipfile` usage。
- Direct XML parsing。
- Direct PyQt widgets。
- Direct `webbrowser.open`。
- Direct image processing。

### Public Contracts

Expected modules:

- `workflow.py`
- `merge_planner.py`
- `export_orchestrator.py`
- `progress.py`
- `settings_service.py`

Example contract:

```python
class ExportOrchestrator:
    def compile_plan(self, request: ExportRequest) -> MergePlan: ...
    def export(self, plan: MergePlan) -> ExportSummary: ...
```

### Test Responsibility

- Use fake ports.
- Test orchestration decisions.
- Do not rely on real 3MF zip unless in integration tests.

## 4. `ports/`

### Responsibility

`ports` defines protocols for external capabilities.

Expected ports:

- `PackageReader`
- `PackageWriter`
- `ConnectLauncher`
- `SettingsStore`
- `Clock`
- `FileSystem` if needed

### Allowed Dependencies

- `typing.Protocol`
- `pathlib.Path`
- domain objects

### Forbidden

- Concrete implementation.
- Runtime side effects.

### Test Responsibility

Ports do not need direct tests unless helper types are introduced.

## 5. `adapters/bambu_3mf/`

### Responsibility

Concrete Bambu 3MF handling:

- Safe archive inspection and extraction。
- Package path resolution。
- XML metadata parsing。
- XML metadata rewriting。
- Package staging and final zip writing。
- Preview composition。

### Allowed Dependencies

- `zipfile`
- `tempfile`
- `shutil`
- `hashlib`
- `json`
- `defusedxml`
- `Pillow` only in preview composer
- `domain`
- `ports`

### Forbidden

- PyQt UI calls。
- Bambu Connect launching。
- Domain policy decisions that belong in `application`。
- Unsafe archive extraction helpers like `ZipFile.extractall` without guard checks。

### Public Contracts

Expected modules:

```text
archive_guard.py
safe_xml.py
metadata_reader.py
metadata_rewriter.py
package_reader.py
package_writer.py
preview_composer.py
```

Expected behavior:

- Any package member path must be validated before writing to disk.
- XML read/write must go through `SafeXmlStore`.
- Metadata rewriting must be deterministic.
- Synthetic fixtures must be enough for automated tests.

### Test Responsibility

- Unit tests for safety checks.
- Integration tests for synthetic 3MF import/export.
- Regression test for old `ET` undefined failure.

## 6. `adapters/gcode/`

### Responsibility

Concrete text processing for G-code:

- Legacy XOR + Base64 compatibility。
- Lightweight command parser。
- Transform stages。
- Pipeline orchestration。
- Golden file fixtures。

### Allowed Dependencies

- `re`
- `base64`
- domain policies and models

### Forbidden

- 3MF zip handling。
- GUI calls。
- Writing output 3MF。
- Broad parser assumptions that rewrite unknown commands。

### Public Contracts

Expected modules:

```text
legacy_crypto.py
parser.py
stages.py
pipeline.py
```

Expected pipeline order:

```text
NormalizeNewlines
StartPositionPatch
ChannelRemap
M73PlateNumberEncode
PlateChangeInsertion
EnsureTrailingNewline
```

### Test Responsibility

- Unit tests for each stage.
- Golden file tests for pipeline output.
- Safety tests for missing markers.

## 7. `adapters/connect/`

### Responsibility

Concrete external application handoff.

Expected module:

- `bambu_connect_launcher.py`

Expected behavior:

```python
build_import_url(file_path: Path, display_name: str | None, version: str) -> str
open_import(file_path: Path, display_name: str | None = None) -> bool
```

### Allowed Dependencies

- `webbrowser`
- `urllib.parse`
- `pathlib.Path`

### Forbidden

- Bambu account handling。
- Cloud API calls。
- Printer control。

## 8. `interfaces/cli/`

### Responsibility

Command-line interface.

Expected commands:

- `inspect`
- `merge`
- `decode-legacy-code`
- `validate-queue`

### Allowed Dependencies

- `argparse` or `typer` if later added。
- application services。
- adapter composition root。

### Forbidden

- Business logic beyond argument parsing and result formatting。
- Direct XML/G-code transforms。

## 9. `interfaces/desktop/`

### Responsibility

PyQt6 desktop app.

Expected modules:

```text
app.py
main_window.py
workers.py
view_models.py
widgets/
```

### Required Design

- Use ViewModels for UI state.
- Use background workers for import/export.
- UI calls application workflow only.
- Long operations emit progress events.

### Forbidden

- Running export synchronously on the main thread。
- Parsing 3MF directly in button click handlers。
- Mutating domain objects from table widget callbacks without ViewModel mediation。

## 10. `resources/`

### Responsibility

Small default resources:

- default plate-change G-code。
- default finish sound G-code。
- default settings JSON。

### Rules

- Resources must be small and text-based unless there is a strong reason.
- No private 3MF files.
- No large binaries.

## 11. `tests/`

### Layout

```text
tests/
  unit/
  integration/
  fixtures/
    gcode/
    3mf/
```

### Rules

- Unit tests should be fast and deterministic.
- Integration tests can create synthetic zip/3MF files in temp directories.
- Fixtures should be minimal and public-safe.
- Do not depend on the old `net9.0-windows7.0` directory.
