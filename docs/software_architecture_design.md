# ChangePlatAutoNext 软件架构设计文档

## 1. 设计目标

ChangePlatAutoNext 是对当前自动换盘工具的重新架构设计。它保留现有业务能力，但重写系统边界，使核心逻辑可测试、可扩展、可复用。

核心目标：

1. **业务核心纯净**：领域模型、队列规划、通道映射、G-code 变换规则不依赖 PyQt、ZIP、XML 或系统调用。
2. **导出流程可验证**：导出前先生成 `MergePlan`，完成所有冲突和安全校验，再进入文件写入阶段。
3. **接口可替换**：同一个核心可被桌面 GUI、CLI、批处理任务调用。
4. **3MF 适配器集中**：Bambu 3MF 包结构、XML 元数据、预览图、MD5、rels 改写集中在 adapter 层，不散落在应用层。
5. **G-code 管线显式化**：每个变换步骤都是一个命名 stage，可单测、可开关、可记录 warning。
6. **错误用户可理解**：所有失败都归类为导入错误、映射错误、G-code 错误、导出错误、外部应用错误，并附带可操作建议。
7. **避免旧项目污染**：不把虚拟环境、发布 EXE、DLL、大体积样例混入新项目源码树。

## 2. 非目标

本项目不做以下事情：

1. 不实现 3D 模型切片。
2. 不直接控制打印机开始打印。
3. 不保存 Bambu 账号、设备 token 或云服务凭据。
4. 不保证跨多个 3MF 的几何模型完整合并；输出 3MF 的实际打印以合并 G-code 为准。
5. 不试图完全复刻 Bambu Studio 的全部私有元数据，只更新后处理所需的最小一致集合。

## 3. 总体架构

采用 Clean Architecture + Pipeline 的结构：

```text
interfaces  ->  application  ->  domain
     |              |             ^
     v              v             |
 adapters  ->     ports  ---------+
```

依赖方向只允许向内：

- `domain` 不依赖任何外层。
- `application` 依赖 `domain` 和 `ports`。
- `adapters` 实现 `ports`，依赖具体技术，如 ZIP、XML、Pillow、webbrowser。
- `interfaces` 是 GUI、CLI、自动化入口，依赖 `application`。

## 4. 推荐目录结构

```text
ChangePlatAutoNext/
  .github/workflows/ci.yml
  docs/
    adr/
    api/
    user/
    vibecoding/
    current_project_understanding.md
    migration_plan.md
    repository_structure.md
    software_architecture_design.md
  examples/
    queue.example.json
  requirements/
    runtime.txt
    desktop.txt
    dev.txt
  resources/
  scripts/
  src/change_plate_next/
    domain/
      models.py
      errors.py
      policies.py
      channel_mapping.py
    application/
      workflow.py
      merge_planner.py
      export_orchestrator.py
      settings_service.py
      progress.py
    ports/
      package.py
      connect.py
      settings.py
      filesystem.py
    adapters/
      bambu_3mf/
        archive_guard.py
        safe_xml.py
        package_reader.py
        package_writer.py
        metadata_reader.py
        metadata_rewriter.py
        preview_composer.py
      gcode/
        parser.py
        pipeline.py
        stages.py
        legacy_crypto.py
      connect/
        bambu_connect_launcher.py
    interfaces/
      cli/
        main.py
      desktop/
        app.py
        main_window.py
        workers.py
        view_models.py
        widgets/
    resources/
  tests/
    unit/
    integration/
    fixtures/
      gcode/
      3mf/
  .gitignore
  CHANGELOG.md
  CONTRIBUTING.md
  LICENSE
  Makefile
  README.md
  pyproject.toml
```

当前已创建最小骨架，后续实现时按此目录继续补齐。

## 5. 领域模型设计

### 5.1 核心对象

| 对象 | 含义 | 不应包含 |
| --- | --- | --- |
| `FilamentSignature` | 用于判断耗材是否可共用实际通道的特征 | GUI 颜色对象、XML 节点 |
| `FilamentUsage` | 某 plate 中一个本地耗材的用量和原始属性 | 文件解析逻辑 |
| `PlateAssetRefs` | plate 关联的 G-code、预览图、top、pick、bbox 等资源路径 | 读写方法 |
| `Plate` | 一个可加入队列的已切片 plate | Qt item、XML element |
| `QueueEntry` | 队列项、copies、本地通道到实际通道映射 | 表格状态 |
| `PlateChangeRecipe` | 换盘和等待策略 | GUI 控件 |
| `MergePlan` | 完整导出计划，中间表示 | 直接打开文件句柄 |
| `ExportSummary` | 导出结果 | 弹窗行为 |

### 5.2 建议新增 `MergePlan`

旧项目的 `export_merged_3mf` 直接执行导出。新项目应先编译计划：

```python
@dataclass(frozen=True, slots=True)
class MergePlan:
    source_packages: tuple[Path, ...]
    target_base_package: Path
    target_plate_index: int
    segments: tuple[GcodeSegmentPlan, ...]
    filament_table: tuple[AggregatedFilament, ...]
    metadata_updates: MetadataUpdatePlan
    preview_plan: PreviewPlan
    output_path: Path
    warnings: tuple[str, ...]
```

计划编译阶段只读必要元数据，不写输出文件。它负责回答：

1. 最终会打印多少盘。
2. 每段 G-code 来自哪里。
3. 每段会应用哪些变换。
4. 最终实际 AMS 通道有哪些。
5. 是否有通道冲突、缺失 G-code、危险插入点。
6. 输出 3MF 需要改哪些元数据。

只有 `MergePlan` 通过校验后，`PackageWriter` 才开始 staging 和写文件。

## 6. 应用层用例

### 6.1 `InspectPackageUseCase`

输入：`.3mf` 路径。

输出：`PackageInspection`：

- source path
- plate list
- import warnings
- package capabilities

职责：

1. 调用 `PackageReader.inspect`。
2. 捕获 adapter 错误并转成用户可理解错误。
3. 不创建 GUI 对象。

### 6.2 `BuildQueueUseCase`

输入：已有队列、导入 plate、用户操作。

职责：

1. 添加 plate。
2. 删除 plate。
3. 上移/下移。
4. 修改 copies。
5. 调用 `ChannelMappingService` 生成默认映射。
6. 输出队列快照和 summary。

### 6.3 `CompileMergePlanUseCase`

输入：queue、recipe、输出路径。

职责：

1. 校验队列非空。
2. 校验 copies 总数大于 0。
3. 校验通道映射。
4. 生成每个 copy 的 `GcodeSegmentPlan`。
5. 聚合 prediction、weight、filament usage。
6. 决定目标 plate index。
7. 生成 metadata update plan。
8. 返回 `MergePlan` 或结构化错误。

### 6.4 `ExportUseCase`

输入：`MergePlan`。

职责：

1. 创建 staging。
2. 复制 base package。
3. 对每个 G-code segment 执行 pipeline。
4. 写目标 G-code 和 MD5。
5. 删除或隔离非目标 plate 的 G-code。
6. 应用 metadata rewriter。
7. 合成预览图。
8. 打包输出 3MF。
9. 返回 `ExportSummary`。

### 6.5 `OpenInBambuConnectUseCase`

输入：输出文件路径、显示名、version。

职责：

1. 调用 `ConnectLauncher.open_import`。
2. 不保存账号信息。
3. 如果失败，返回可显示错误。

## 7. 3MF Adapter 设计

### 7.1 `ArchiveGuard`

负责安全读取 zip/3MF：

| 策略 | 默认值 |
| --- | --- |
| max files | 5000 |
| max uncompressed bytes | 1GB |
| max single file bytes | 512MB |
| max XML bytes | 64MB |
| max compression ratio | 200 |
| reject absolute path | true |
| reject `..` path segment | true |
| reject backslash in member name | true |
| reject symlink member | true |
| verify CRC | true |

`ArchiveGuard` 应提供：

```python
inspect_zip(path: Path) -> ArchiveManifest
extract_to(path: Path, target_dir: Path) -> ArchiveManifest
```

这样导入 UI 可以先显示包体信息，导出也能复用安全策略。

### 7.2 `MetadataReader`

负责读取：

- `Metadata/slice_info.config`
- `Metadata/model_settings.config`
- `Metadata/filament_sequence.json`
- `_rels/.rels`
- `[Content_Types].xml`，必要时只保留

输出统一的 `Plate` 和 `PackageMetadata` 对象。

读取策略：

1. XML 使用同一个 `SafeXml` 组件。
2. 路径统一经过 package path resolver。
3. 允许缺失非关键元数据，但产生 warning。
4. 对缺失 `plate_N.gcode` 的已切片判定必须明确。

### 7.3 `MetadataRewriter`

负责把 `MetadataUpdatePlan` 应用到 staging：

| 文件 | 更新策略 |
| --- | --- |
| `slice_info.config` | 只保留目标 plate，更新 prediction、weight、filament_maps、limit_filament_maps、filament 节点 |
| `model_settings.config` | 只保留或重写目标 plate 的 gcode/preview/top/pick/bbox 路径 |
| `_rels/.rels` | 更新指向目标 plate 资源的 Target，保留其他必要关系 |
| `filament_sequence.json` | 更新目标 plate 通道序列 |
| `plate_N.gcode.md5` | 按 UTF-8 文本重新计算 MD5 |

注意：新项目必须消除旧项目中 `ET`/`StdET` 混用问题。所有 XML 读写统一使用一个模块，例如：

```python
class SafeXmlStore:
    def parse_file(self, path: Path) -> ElementTree: ...
    def parse_bytes(self, data: bytes, label: str) -> ElementTree: ...
    def write(self, tree: ElementTree, path: Path) -> None: ...
```

### 7.4 `PackageWriter`

`PackageWriter` 只做文件级执行，不决定业务规则。

执行阶段：

1. 创建临时目录。
2. 复制 base package root 到 staging。
3. 调用 `GcodePipeline` 生成合并 G-code。
4. 写目标 G-code。
5. 写 MD5。
6. 调用 `PreviewComposer`。
7. 调用 `MetadataRewriter`。
8. 删除多余 G-code 或移动到 `Metadata/unused/`，具体策略由 plan 决定。
9. zip 打包输出。
10. 清理临时目录。

## 8. G-code 管线设计

### 8.1 管线结构

G-code 处理应拆成 stages：

```text
ReadText
  -> NormalizeNewlines
  -> StartPositionPatch
  -> ChannelRemap
  -> M73PlateNumberEncode
  -> PlateChangeInsertion
  -> EnsureTrailingNewline
```

每个 stage 输入输出：

```python
@dataclass(frozen=True)
class GcodeTransformInput:
    text: str
    segment: GcodeSegmentPlan
    context: GcodeTransformContext

@dataclass(frozen=True)
class GcodeTransformOutput:
    text: str
    warnings: tuple[str, ...]
    metrics: dict[str, int]
```

优点：

1. 每个规则都可以单测。
2. 日志可以记录每段应用了哪些 stage。
3. GUI 可以显示 warning 来源。
4. 未来可以新增机型规则而不改导出主流程。

### 8.2 G-code command 识别

当前实现使用 regex 逐行处理，这足够实用。新项目建议保持轻量 parser，而不是引入复杂 G-code AST。

识别原则：

1. 注释行不改。
2. 空行不改。
3. 只改安全白名单命令。
4. 保留原始行尾注释。
5. 对未知命令不改。

通道重写白名单：

| 命令 | 示例 | 处理 |
| --- | --- | --- |
| `M620` | `M620 S0A`、`M620 S0 A`、`M620 S0` | 重写 S 参数 |
| `M621` | `M621 S1 A` | 重写 S 参数 |
| `Tn` | `T0` | 重写工具号 |

保留工具号：

- `255`
- `1000`

### 8.3 换盘插入策略

建议定义枚举：

```python
class InsertionStrategy(Enum):
    BEFORE_FINISH_SOUND_BLOCK = "before_finish_sound_block"
    AFTER_FINISH_SOUND_BLOCK = "after_finish_sound_block"
    APPEND_WITH_WARNING = "append_with_warning"
    FAIL_FAST = "fail_fast"
```

默认策略：`BEFORE_FINISH_SOUND_BLOCK + FAIL_FAST`。

UI 文案应明确：如果找不到结束音乐标记，默认中止生成，因为错误插入换盘 G-code 可能导致打印头、热床或料盘运动风险。

### 8.4 机型规则

当前硬编码 `G0 Y254 F3000 -> G0 Y250 F3000 ;XKY ADD`。

新项目建议：

```python
@dataclass(frozen=True)
class GcodePatchRule:
    name: str
    machine_scope: tuple[str, ...]
    match_exact_line: str
    replacement_line: str
    required: bool = False
```

默认规则可以命名为：`bambu_a1_start_y_safety_offset`。

## 9. 通道映射设计

### 9.1 通道模型

区分三个概念：

| 概念 | 说明 |
| --- | --- |
| local filament id | `slice_info.config` 中每个 plate 内部的 `filament id`，通常 1 起始 |
| G-code tool index | G-code 中 `T0`、`M620 S0` 的工具号，通常 0 起始 |
| actual AMS channel | 用户真实装料通道，界面显示 1 起始 |

转换规则：

```text
local filament id 1 -> G-code tool 0
actual AMS channel 3 -> G-code tool 2
```

### 9.2 自动分配策略

默认 signature：

```text
color + material + nozzle_diameter
```

比旧项目多纳入 `nozzle_diameter`，原因是不同喷嘴直径或体积类型在某些配置下可能不应混用。

可选增强 signature：

- vendor
- tray_info_idx
- temperature profile
- support/object usage

这些作为高级选项，不影响第一版。

### 9.3 冲突策略

同一实际 AMS 通道下：

- color 不同：阻止导出。
- material 不同：阻止导出。
- nozzle_diameter 不同：默认阻止导出，可由专家模式覆盖。
- 同色同料但 tray_info_idx 不同：警告，由用户确认。

### 9.4 UI 展示

GUI 应展示两张表：

1. 实际装料通道表：通道、颜色、材料、喷嘴、总克重、来源、状态。
2. Plate 本地通道表：队列项、源文件、plate、local id、检测颜色、材料、用量、装到通道。

导出按钮只有在映射有效时才可用，或导出时给出明确阻断错误。

## 10. 设置系统设计

### 10.1 配置来源优先级

从低到高：

1. 内置默认值。
2. `resources/default_settings.json`。
3. 用户配置文件。
4. 当前会话 UI 修改。
5. CLI 参数。

### 10.2 用户配置位置

不建议继续默认写入源码目录的 `config/settings.json`。推荐：

| 系统 | 路径 |
| --- | --- |
| macOS | `~/Library/Application Support/ChangePlatAutoNext/settings.json` |
| Windows | `%APPDATA%/ChangePlatAutoNext/settings.json` |
| Linux | `~/.config/change-plate-next/settings.json` |

源码树中的 `resources/default_settings.json` 只作为默认资源。

### 10.3 G-code 片段管理

建议保存为 profile：

```json
{
  "profiles": [
    {
      "id": "default-a1",
      "name": "Bambu A1 default plate change",
      "machine_scope": ["A1", "A1 mini"],
      "change_gcode": "...",
      "sound_gcode": "..."
    }
  ],
  "active_profile_id": "default-a1"
}
```

这样用户可以维护慢速/快速/实验版本，不必反复覆盖同一段文本。

## 11. 桌面 UI 设计

### 11.1 UI 分区

建议主界面分为五个区域：

1. **导入与队列**：文件列表、plate 列表、copies、顺序。
2. **装料通道**：实际通道和本地通道映射。
3. **换盘策略**：G-code profile、热床降温、等待、提示音、插入策略。
4. **导出预检**：总盘数、总耗时、总重量、warning、阻断错误。
5. **执行日志**：导入、计划、导出、Bambu Connect handoff。

### 11.2 线程模型

导入和导出都可能处理大 zip 和大 G-code，必须使用后台 worker。

```text
MainWindow
  -> WorkflowViewModel
  -> BackgroundWorker
  -> Application UseCase
  -> ProgressEvent stream
  -> MainWindow update
```

进度事件建议：

```python
@dataclass(frozen=True)
class ProgressEvent:
    phase: Literal["import", "plan", "transform", "metadata", "pack", "connect"]
    current: int
    total: int
    message: str
```

GUI 不直接调用 adapter，而是调用 application workflow。

### 11.3 错误展示

错误分三层展示：

| 类型 | UI 行为 |
| --- | --- |
| warning | 显示在预检面板和日志，不阻止导出 |
| blocking validation error | 禁用导出或弹出可修复提示 |
| unexpected error | 弹出详细错误，可复制 traceback 到日志 |

### 11.4 Modern QSS Theme

桌面端使用 PyQt6 Widgets + QSS。视觉规范定义在 `docs/user/modern_ui_design.md`，第一版主题为 `Workshop Light`。

实现约束：

1. QSS 文件放在 `src/change_plate_next/interfaces/desktop/styles/`。
2. `ThemeManager` 或 `theme.py` 负责统一加载 QSS。
3. 禁止在业务逻辑中散写 `setStyleSheet`。
4. 使用 objectName 和 dynamic properties 表示特殊组件和状态。
5. 冲突、警告和成功状态必须同时有颜色和文字说明。
6. 大任务必须通过 worker 更新进度，不允许阻塞主线程。

## 12. CLI 设计

CLI 第一版建议支持：

```bash
change-plate-next inspect input.3mf
change-plate-next merge input.3mf --all-plates --output merged.3mf
change-plate-next merge a.3mf b.3mf --queue queue.json --output merged.3mf
change-plate-next decode-legacy-code net9.0-windows7.0/code.rar
```

`queue.json` 示例：

```json
{
  "items": [
    {"source": "a.3mf", "plate": 1, "copies": 2, "channel_map": {"1": 1}},
    {"source": "b.3mf", "plate": 1, "copies": 1, "channel_map": {"1": 2}}
  ],
  "recipe": {
    "profile": "default-a1",
    "wait_hotbed_cool": false,
    "wait_before_next_plate": true,
    "wait_seconds": 120
  }
}
```

CLI 能给核心能力带来两个好处：

1. 易于回归测试。
2. 用户可以批量处理任务。

## 13. 错误类型设计

建议错误树：

```text
ChangePlateError
  InvalidThreeMfError
    UnslicedThreeMfError
    UnsafeArchiveError
    MissingMetadataError
  ChannelMappingError
    ChannelConflictError
    ChannelLimitExceededError
  GcodeTransformError
    FinishMarkerMissingError
    UnsafeInsertionPointError
  ExportError
    StagingError
    MetadataRewriteError
    PackageWriteError
  ConnectLaunchError
```

每个错误包含：

- `message`: 面向用户。
- `technical_detail`: 面向日志。
- `suggestion`: 可操作建议。
- `severity`: warning/error/fatal。

## 14. 日志与可观测性

每次导出生成一个 `ExportReport`：

```json
{
  "source_packages": [],
  "output_path": "...",
  "total_printed_plates": 3,
  "gcode_segments": [],
  "filament_channels": [],
  "warnings": [],
  "metadata_files_updated": [],
  "created_at": "..."
}
```

默认写入用户配置目录下的 `logs/`，GUI 中也展示摘要。

这个 report 对排查问题很有用，尤其是用户反馈“颜色不对”或“Bambu Connect 识别不对”时。

## 15. 测试策略

### 15.1 单元测试

| 模块 | 测试重点 |
| --- | --- |
| `domain.channel_mapping` | 自动分配、冲突、通道上限、signature 归一化 |
| `adapters.gcode.parser` | M620/M621/Tn 识别、注释跳过、保留行尾注释 |
| `adapters.gcode.stages` | 起始位置修正、M73 编码、插入策略、等待片段构造 |
| `adapters.gcode.legacy_crypto` | XOR + Base64 往返、BOM 处理 |
| `adapters.bambu_3mf.archive_guard` | 路径穿越、zip bomb、symlink、文件数限制 |
| `adapters.bambu_3mf.metadata_reader` | plate 和 filament 解析、未切片识别 |
| `adapters.bambu_3mf.metadata_rewriter` | slice_info、model_settings、rels、filament_sequence 改写 |

### 15.2 集成测试

建立小型 synthetic 3MF fixtures：

1. single plate, single filament。
2. multi plate, same filament。
3. multi plate, different color, requires remap。
4. package without gcode, should raise `UnslicedThreeMfError`。
5. package with malicious zip path, should raise `UnsafeArchiveError`。
6. package missing finish sound marker, should fail fast。
7. package with model_settings custom gcode path。
8. package with filament_sequence.json。

### 15.3 Golden file 测试

对 G-code pipeline 使用 golden files：

```text
tests/fixtures/gcode/channel_remap/input.gcode
tests/fixtures/gcode/channel_remap/expected.gcode
```

这样后续调整 regex 或 parser 时能快速发现行为变化。

### 15.4 当前回归基线

当前旧项目有一个已知失败：`threemf.py` 中 `ET` 未定义。新项目迁移第一步应写一个覆盖 rels/model_settings 改写的测试，确保这个问题不会复现。

## 16. 兼容性设计

### 16.1 旧版片段兼容

保留导入：

- `net9.0-windows7.0/code.rar`
- `net9.0-windows7.0/sound.rar`

导入后立刻转换为明文 profile，不再以 `.rar` 格式保存。

### 16.2 旧版设置兼容

可提供一次性迁移器读取 `set.ini`：

```text
WaitHotbedCool -> wait_hotbed_cool
HotbedTemp -> hotbed_temp
WaitBeforeNextPlate -> wait_before_next_plate
WaitTime -> wait_seconds
SoundTipWhenWait -> sound_tip_when_waiting
SountTipCount -> sound_tip_count
TimeLeftAsPlateNo -> encode_plate_number_in_m73
PlateChangeFlag -> plate_change_marker
```

迁移器输出 `settings.json` 和 profile。

## 17. 安全设计

### 17.1 文件安全

1. 所有导入 zip 必须经过 `ArchiveGuard`。
2. 所有 package 内路径必须通过 resolver。
3. 输出路径不允许覆盖输入文件，除非用户明确确认。
4. 导出先写临时文件，成功后原子替换或移动到目标。
5. 清理临时目录失败时记录 warning，不吞掉主结果。

### 17.2 G-code 安全

1. 默认 fail fast，不在未知位置插入换盘代码。
2. 高风险选项需要 UI 明示，例如“找不到结束标记时仍追加到末尾”。
3. 每个内置 profile 标注适用机型。
4. 输出前显示总盘数和预计耗时。
5. 对启用 M73 编码、起始位置修正等非官方技巧显示说明。

### 17.3 外部应用安全

Bambu Connect 集成只打开本地文件导入 URL，不处理账号、云 API 或打印授权。

## 18. 性能设计

1. G-code 以文本分段处理，单个 plate 读入内存是可接受的；超大文件可后续改为流式 stage。
2. zip staging 使用文件复制，避免在内存中构造整个 3MF。
3. 预览图合成最多使用 512x512 canvas，不应造成明显内存压力。
4. 导入多个 3MF 可以并行读取，但初版建议串行，降低临时目录竞争风险。
5. GUI 导出必须后台执行，避免窗口无响应。

## 19. 输出一致性策略

导出后的 3MF 应满足：

1. 包内存在目标 `Metadata/plate_{target}.gcode`。
2. 包内存在对应 `Metadata/plate_{target}.gcode.md5`。
3. `slice_info.config` 中只保留目标 plate 或至少目标 plate 与 gcode 一致。
4. `prediction` 等于所有 copies 的预测时间总和。
5. `weight` 等于所有 copies 的重量总和。
6. `filament` 节点按实际 AMS 通道聚合。
7. `filament_sequence.json` 与实际使用通道一致。
8. `model_settings.config` 指向目标 G-code 和预览图。
9. `_rels/.rels` 不再指向已删除的 plate G-code。
10. Bambu Connect 能识别并导入输出文件。

## 20. 实施优先级

### P0: 核心可用

1. 迁移 domain models。
2. 实现 `ArchiveGuard`。
3. 实现 `MetadataReader`。
4. 实现 G-code pipeline。
5. 实现 `MergePlanner`。
6. 实现 `PackageWriter`。
7. 用 synthetic fixtures 跑通导出。

### P1: 桌面可用

1. PyQt6 主窗口重建。
2. 后台 worker 和进度展示。
3. 队列与通道映射 view model。
4. G-code profile 编辑器。
5. Bambu Connect handoff。

### P2: 体验和兼容

1. 旧版 `set.ini` 迁移。
2. 多 profile 管理。
3. 导出报告。
4. CLI 完整参数。
5. 更丰富的 3MF fixtures。

## 21. 架构决策记录

### ADR-001: 保持 Python + PyQt6

原因：当前核心已有 Python 实现，测试和跨平台开发成本低。PyQt6 能满足桌面 UI 需求。旧 .NET 发布物不作为新源码基础。

### ADR-002: 不直接使用 Bambu 云 API

原因：账号和设备授权属于高风险边界。使用 Bambu Connect URL handoff 可借助官方客户端完成账号和设备确认。

### ADR-003: 先计划后执行

原因：当前导出函数边验证边写文件，错误发现较晚。`MergePlan` 可让 GUI 在写文件前展示完整预检结果，并让测试更简单。

### ADR-004: G-code 采用白名单文本变换

原因：完整 G-code AST 成本高且收益有限。当前需求只需识别少量命令，白名单逐行变换更透明也更安全。

### ADR-005: 3MF metadata adapter 集中实现

原因：Bambu 3MF 的内部文件互相关联。把改写逻辑集中到 adapter 可以防止 `slice_info`、`model_settings`、`rels`、`filament_sequence` 行为分散并互相矛盾。

## 22. 第一版完成定义

第一版 ChangePlatAutoNext 可认为完成，当且仅当：

1. 可导入当前样例已切片 3MF。
2. 可导入多个 plate 并生成合并 3MF。
3. 可自动映射不同颜色耗材到不同实际通道。
4. 可检测并阻止通道冲突。
5. 可插入默认换盘 G-code。
6. 可更新 MD5 和核心 metadata。
7. 可通过 Bambu Connect URL 打开输出文件。
8. 所有 P0 单元和集成测试通过。
9. GUI 导入导出不阻塞主线程。
10. 文档说明未切片 3MF、跨文件合并限制和高风险 G-code 选项。

## 23. License Strategy

ChangePlatAutoNext uses `GPL-3.0-only` because the selected desktop framework is PyQt6. PyQt6 open-source releases are GPL v3, and Riverbank offers a commercial license for proprietary distribution.

Rules:

1. Source distributions include `LICENSE` and GPL notices.
2. About dialog displays `GPL-3.0-only` and PyQt6 license note.
3. Packaging documentation must distinguish open-source GPL distribution from commercial closed-source distribution.
4. If the project later changes to another Qt binding, license policy must be revisited through a new ADR.
