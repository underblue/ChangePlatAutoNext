# 当前项目理解文档

本文档记录对 `/Users/lujieran/Project/ChangePlatAuto` 当前项目的整体理解，覆盖目录结构、核心业务流程、数据模型、旧版兼容逻辑、测试状态和已知风险。它的作用是给新项目设计提供可追溯依据。

## 1. 项目定位

当前软件是一个面向 Bambu 已切片 3MF 文件的 G-code 后处理工具。它不负责切片，也不重新生成几何模型，而是在 3MF 包内已经存在 `Metadata/plate_N.gcode` 的前提下，完成以下工作：

1. 读取一个或多个已切片 3MF。
2. 把其中的 plate 加入打印队列。
3. 允许用户设置每个 plate 打印次数。
4. 对多色打印进行本地耗材通道到实际 AMS 通道的映射。
5. 串接各 plate 的 G-code。
6. 在每段 G-code 中插入自动换盘代码。
7. 更新 3MF 包里的 G-code、MD5、预览图和部分元数据。
8. 重新打包成新的 3MF。
9. 导出后可通过 `bambu-connect://` URL scheme 交给 Bambu Connect。

这个工具的本质不是 slicer，而是面向 Bambu 3MF 包结构的后处理器和合并器。

## 2. 目录结构理解

| 路径 | 作用 | 维护判断 |
| --- | --- | --- |
| `change_plat_auto/` | 当前 Python + PyQt6 实现，包含核心处理、配置、GUI、Bambu Connect 集成 | 主要可维护源码 |
| `config/` | 默认换盘 G-code、提示音 G-code、默认设置示例 | 运行时配置和默认资源 |
| `tests/` | 核心单元测试 | 有价值，但覆盖不完整 |
| `docs/pyqt6_rewrite_design.md` | 已有 PyQt6 重写设计说明 | 可作为历史设计参考 |
| `docs/reverse_engineering.md` | 当前为空 | 可由新文档替代 |
| `BASE64_coder/` | 旧版 `code.rar`/`sound.rar` 的 XOR + Base64 解码/再编码脚本和样例 | 旧版兼容工具 |
| `net9.0-windows7.0/` | 旧版 .NET 9 Windows 发布目录、DLL、EXE、样例 File 目录、配置 | 历史运行产物，非主要源码 |
| `path/to/venv/` | 嵌入项目的 Python 虚拟环境 | 不应纳入新项目代码管理 |
| `run_pyqt6_app.py` | 当前 PyQt6 GUI 启动脚本 | 入口脚本 |

当前目录体积约 435MB，其中 `net9.0-windows7.0` 约 172MB，`path/to/venv` 是主要冗余来源之一。新项目应避免把虚拟环境、运行库、二进制发布物混入源码树。

## 3. 当前 Python 模块职责

| 模块 | 职责 |
| --- | --- |
| `models.py` | 定义 `FilamentInfo`、`PlateInfo`、`ThreeMFProject`、`QueueItem`、`ProcessOptions`、`ExportResult` |
| `config.py` | 加载和保存 JSON 设置，读取默认 G-code 文件，兼容旧版加密片段 |
| `crypto.py` | 对旧版 `code.rar` 做 XOR + Base64 解密和加密，读取明文 G-code |
| `gcode.py` | G-code 文本规范化、换盘代码构造、起始位置修正、M73 编码、通道重映射、换盘代码插入、耗材聚合和映射校验 |
| `threemf.py` | 安全解包 3MF、解析 `slice_info.config`、解析 `model_settings.config`、导出合并 3MF、更新相关元数据 |
| `bambu_connect.py` | 构造 `bambu-connect://import-file` URL 并用系统默认方式打开 |
| `gui/main_window.py` | PyQt6 主窗口，管理导入、队列、选项、导出和 Bambu Connect 交互 |
| `gui/channel_mapping.py` | 实际装料通道表和本地通道归属表 |
| `gui/gcode_editor.py` | 换盘 G-code、提示音 G-code 的 GUI 编辑、导入和保存 |

当前设计已经有一个好的方向：核心层不依赖 Qt，GUI 基本只做输入输出。但仍有几个问题：编排逻辑集中在 `threemf.export_merged_3mf`，3MF 读写、G-code 管线、元数据重写和预览图合成耦合在一起；错误类型不够分层；新入口还没有 CLI 或批处理边界。

## 4. 配置与旧版兼容

### 4.1 新版配置

`config/default_settings.json` 使用文件引用方式加载默认 G-code：

```json
{
  "change_gcode_file": "default_change_plate.gcode",
  "sound_gcode_file": "default_finish_sound.gcode",
  "hotbed_temp": 40,
  "wait_seconds": 120,
  "sound_tip_count": 10,
  "bambu_connect_version": "1.0.0"
}
```

`config.py` 会把 `change_gcode_file` 和 `sound_gcode_file` 展开为实际文本。用户保存后写入 `config/settings.json`，保存的是完整 `AppSettings` 数据。

### 4.2 旧版配置

旧版 `net9.0-windows7.0/set.ini` 包含关键选项：

| 旧配置项 | 当前含义 |
| --- | --- |
| `WaitHotbedCool` | 是否等待热床降温 |
| `HotbedTemp` | 热床目标温度，默认 40 |
| `WaitBeforeNextPlate` | 退盘后是否等待 |
| `WaitTime` | 等待秒数，默认 120 |
| `SoundTipWhenWait` | 等待时是否循环提示音 |
| `SountTipCount` | 提示音次数，旧版拼写如此 |
| `TimeLeftAsPlateNo` | 是否通过 M73 R 高位编码当前盘号 |
| `PlateChangeFlag` | 换盘片段标记，默认 `;start change plate` |
| `Postion1` / `Postion1_edit` | A1 起始 Y 位置修正规则 |

旧版 `code.rar` 实际是带 UTF-8 BOM 的 Base64 文本，内容经过 `MySecureKey123` 循环 XOR。`crypto.py` 和 `BASE64_coder/` 里的脚本实现了解码兼容。新项目仍应保留“导入旧版片段”的能力，但不应把旧版加密格式作为主要配置格式。

## 5. 3MF 导入流程

当前入口是 `extract_3mf(path, workspace_dir=None)`。

流程如下：

1. 校验后缀必须是 `.3mf`。
2. 校验源文件存在。
3. 创建临时工作目录，默认在系统 temp 下的 `change_plat_auto_pyqt`。
4. 调用 `safe_extract_3mf` 安全解包。
5. 调用 `parse_slice_info` 解析 plate。
6. 如果没有可用 plate，则通过 `_describe_missing_gcode` 生成可操作错误信息。
7. 返回 `ThreeMFProject`，其中包含源路径、解包根目录和 plate 列表。

### 5.1 安全解包策略

当前 `safe_extract_3mf` 已经实现了重要保护：

| 检查项 | 当前策略 |
| --- | --- |
| CRC | 使用 `archive.testzip()` 检查 |
| 文件数量 | 最大 5000 |
| 总解压体积 | 最大 1GB |
| 单文件大小 | 最大 512MB |
| 压缩比 | 最大 200 |
| 路径穿越 | 拒绝绝对路径、`../`、空路径段、反斜杠 |
| 符号链接 | 拒绝 symlink member |

这些规则应该迁移到新项目的 `ArchiveGuard` 或 `SafeZipExtractor` 中，并保持可测试。

### 5.2 XML 解析策略

当前优先使用 `defusedxml.ElementTree`。如果没有安装 `defusedxml`，会退回标准库，但在解析前拒绝包含 `DOCTYPE` 或 `ENTITY` 的 XML。`MAX_XML_BYTES` 为 64MB。

这条策略正确，下一代架构应把它抽成独立 XML port/adapter，避免多个元数据改写函数各自调用不一致的 XML 解析方式。

### 5.3 已切片 3MF 判定

当前工具要求包内有：

- `Metadata/slice_info.config`
- 与 `slice_info.config` 中 plate index 对应的 `Metadata/plate_N.gcode`

如果 3MF 里存在 `3D/*.model` 和 `Metadata/plate_*.png`，但没有 `Metadata/plate_*.gcode`，当前代码认为这是未切片 3MF，并提示用户先在 Bambu Studio 或 Orca Slicer 中切片。

这是重要业务边界，新项目必须保留并在 UI 上直接解释清楚。

## 6. Plate 解析逻辑

`parse_slice_info` 读取 `Metadata/slice_info.config`：

- 每个 `<plate>` 通过 `<metadata key="index" value="N"/>` 获取 plate index。
- `prediction` 转成秒数。
- `weight` 转成克重。
- `<filament>` 节点转成 `FilamentInfo`。

同时 `_model_settings_plate_metadata` 读取 `Metadata/model_settings.config`，用于补充路径：

| key | 含义 | 默认 fallback |
| --- | --- | --- |
| `gcode_file` | G-code 文件 | `Metadata/plate_N.gcode` |
| `thumbnail_file` | plate 预览图 | `Metadata/plate_N.png` |
| `thumbnail_no_light_file` | 小预览图，当前 fallback 不完全准确 | `Metadata/plate_N_small.png` |

注意：实际 Bambu 包里常见 `thumbnail_no_light_file` 是 `Metadata/plate_no_light_N.png`，当前 `PlateInfo.small_preview_path` 的 fallback 是 `plate_N_small.png`，但导出阶段写的是 `plate_N_small.png`。新设计需要统一预览图资产模型，不要用一个字段混用 no-light 和 small-preview 两种概念。

## 7. G-code 处理逻辑

### 7.1 换盘 G-code 构造

`build_change_gcode(options)` 基于 GUI 选项构造最终插入片段：

1. 规范换行。
2. 如启用热床降温，在片段前添加 `M190 S{temp}`，最低 40。
3. 如启用退盘后等待：
   - 若启用声音提示，则按 `sound_tip_count` 把总等待时间分段，每段先播放提示音再 `G4 P{step_ms}`。
   - 否则追加单条 `G4 P{wait_seconds * 1000}`。
4. 保证末尾有换行。

### 7.2 起始位置修正

`apply_start_fixes` 默认查找完全等于 `G0 Y254 F3000` 的行，并替换为：

```gcode
G0 Y250 F3000 ;XKY ADD
```

如果未找到，会添加警告。这是面向 A1 的经验修正规则。新架构应把它做成可配置 `GcodePatchRule`，并给出启用条件、适用机型和安全说明。

### 7.3 M73 盘号编码

`encode_plate_number_in_m73` 会匹配：

```text
M73 P{progress} R{remaining}
```

并把 `R` 加上 `6000 * plate_number`。这是一种在剩余时间字段高位中显示当前盘号的技巧。新项目应该把它命名为“可选显示编码”，并明确它不是 Bambu 官方语义。

### 7.4 多色通道重映射

当前重写范围：

- `M620 S0A`
- `M620 S0 A`
- `M620 S0`
- `M621 S0A`
- `M621 S0 A`
- `M621 S0`
- 独立工具选择行 `T0`

注释行不重写。`T255`、`T1000`、`M620 S255` 等保留工具号不重写。

映射规则：

```text
G-code tool index = slice_info filament id - 1
new G-code tool index = actual AMS channel - 1
```

例如本地耗材 id 1 映射到 AMS 通道 3，G-code 中 `T0` 会变成 `T2`。

### 7.5 换盘代码插入点

`insert_change_gcode` 默认要求源 G-code 中有两个结束音乐标记：

```gcode
;=====printer finish  sound=========
```

插入逻辑：

- 如果源 G-code 已包含 `;start change plate`，认为已经插入过，直接返回。
- 如果 `insert_after_finish_sound=True`，直接追加到文件末尾。
- 否则查找最后一个结束音乐标记，再查找它之前的前一个结束音乐标记，把换盘代码插在前一个标记之前。
- 如果找不到足够标记，默认抛出 `GcodeInsertionError`，避免危险位置插入。

当前 `ProcessOptions` 有 `allow_append_when_finish_marker_missing`，但 `export_merged_3mf` 调用 `insert_change_gcode` 时没有传这个字段，因此 GUI 实际不能启用这个容错路径。新设计需要把插入策略显式化：`BEFORE_FINISH_SOUND_BLOCK`、`AFTER_FINISH_SOUND_BLOCK`、`APPEND_WITH_WARNING`、`FAIL_FAST`。

## 8. 通道映射与耗材聚合

### 8.1 自动映射

`auto_assign_channels` 按 `FilamentInfo.signature` 分配实际装料通道。signature 是：

```text
(color.upper(), filament_type.upper())
```

同色同材料复用同一个实际通道，不同 signature 依次分配新通道。默认最多 16 个通道。

### 8.2 冲突校验

`validate_channel_assignments` 按实际通道聚合 signature。如果同一个通道被映射到多个颜色或材料，则返回冲突信息。导出前会阻止生成。

### 8.3 耗材聚合

`aggregate_filaments` 会把每个 queue item 的耗材按实际通道聚合：

- `used_m` 和 `used_g` 乘以 copies 后累加。
- 输出的 `FilamentInfo.local_id` 变成实际通道号。
- 保留首个耗材的 `tray_info_idx` 和 extra attributes。

这用于更新目标 3MF 的 `slice_info.config`。

## 9. 导出流程

当前入口是 `export_merged_3mf(queue, options, output_path)`。

完整流程：

1. 校验队列非空。
2. 校验通道映射无冲突。
3. 计算总打印盘数，必须大于 0。
4. 使用队列第一项的 3MF 解包目录作为基底。
5. 目标 plate index 使用第一项 plate index。
6. 创建临时 staging 目录并复制第一项 package root。
7. 构造最终换盘 G-code。
8. 遍历队列和 copies：
   - 读取原始 `plate_N.gcode`。
   - 应用起始位置修正。
   - 应用通道重映射。
   - 如启用，应用 M73 盘号编码。
   - 插入换盘 G-code。
   - 加入合并片段列表。
9. 合并文本写入 staging 中的目标 `Metadata/plate_{target_index}.gcode`。
10. 重新计算并写入 `plate_N.gcode.md5`。
11. 合成或复制预览图。
12. 删除其他 `plate_*.gcode` 和对应 md5。
13. 更新 `slice_info.config`，只保留目标 plate，更新 prediction、weight、filament_maps、filament 节点。
14. 更新 `_rels/.rels` 中指向 plate 的路径。
15. 更新 `model_settings.config` 中的 `gcode_file`。
16. 更新 `filament_sequence.json`。
17. 重新 zip 打包成输出 3MF。
18. 返回 `ExportResult`。

## 10. GUI 工作逻辑

`MainWindow` 初始化时：

1. 调用 `load_settings()`。
2. 创建队列表、日志框、G-code 编辑器、通道映射 widget、选项 widget。
3. 构建左右分栏界面。

用户导入 3MF 时：

1. 文件对话框选择一个或多个 `.3mf`。
2. 对每个路径调用 `extract_3mf`。
3. 每个解析出的 plate 作为 `QueueItem(copies=1)` 加入队列。
4. 调用 `auto_assign_channels`。
5. 刷新队列表和映射表。

用户导出时：

1. 校验队列非空。
2. 文件对话框选择输出路径。
3. 保存选项和 G-code 片段到 `config/settings.json`。
4. 组装 `ProcessOptions`。
5. 调用 `export_merged_3mf`。
6. 日志输出警告。
7. 弹窗询问是否交给 Bambu Connect。
8. 如确认，调用 `launch_bambu_connect`。

GUI 的优点是流程清楚，缺点是导出过程在 UI 线程执行，处理大文件时可能卡住。新项目应使用后台任务、进度事件和可取消执行。

## 11. Bambu Connect 集成

当前 `build_import_url` 构造：

```text
bambu-connect://import-file?path=<absolute path>&name=<display name>&version=1.0.0
```

通过 `webbrowser.open` 打开。这个方案避免在工具内保存 Bambu 账号和设备凭据，是合理边界。新项目可以保留为 `ConnectLauncher` adapter。

## 12. 测试状态

运行命令：

```bash
python -m unittest discover -s tests -v
```

结果：7 个测试中 6 个通过，1 个失败。

失败项：

```text
test_export_synthetic_3mf_with_channel_remap
NameError: name 'ET' is not defined
```

原因：`threemf.py` 中 `_update_rels` 和 `_update_model_settings` 使用 `ET.parse`，但顶部只导入了：

```python
from xml.etree import ElementTree as StdET
```

没有定义 `ET`。这是一个真实可复现问题。新项目需要：

1. 统一 XML 解析依赖，不混用 `ET` 和 `StdET`。
2. 把元数据改写纳入单元测试。
3. 把 synthetic 3MF 测试升级为多个 fixtures，覆盖 rels、model_settings、filament_sequence、preview 和缺失元数据场景。

另外，直接运行：

```bash
python -m unittest -v
```

没有发现测试，因为没有指定 discovery 目录。新项目应使用 `pytest` 或明确配置 unittest discovery，避免“0 tests ran”的假绿灯。

## 13. 已知设计风险

| 风险 | 说明 | 新项目建议 |
| --- | --- | --- |
| 3MF 包结构耦合强 | 当前导出函数同时处理 ZIP、XML、G-code、图片 | 拆成 PackageReader、PackageWriter、MetadataRewriter、GcodePipeline |
| XML API 混用 | `ET` 未定义导致测试失败 | 建立统一 `XmlDocumentStore` |
| GUI 阻塞 | 大 3MF 导入导出会在 UI 线程执行 | 使用后台 worker 和进度事件 |
| 预览图概念混用 | `small_preview_path`、`plate_no_light_N`、`plate_N_small` 含义不清 | 建立 `PlateAssetRefs` 明确字段 |
| 插入策略隐藏 | `allow_append_when_finish_marker_missing` 没有从 GUI 传入 | 显式化插入策略并展示风险 |
| 通道 signature 粒度可能不够 | 只比较颜色和材料，未比较喷嘴、厂商、温度等 | signature 可扩展，并允许用户覆盖 |
| 输出 3MF 几何与 G-code 不完全一致 | 跨文件合并时以第一个 3MF 为基底 | 文档和 UI 明确“以 G-code 为准，模型预览为合成展示” |
| 没有作业中间表示 | 导出直接边读边写 | 引入 `MergePlan`，先验证再执行 |
| 缺少 CLI | 不利于批处理和自动化测试 | 新项目保留 CLI entrypoint |
| 项目树混有二进制和虚拟环境 | 体积大，难维护 | 新项目只纳入源码、测试、文档和小型 fixtures |

## 14. 新项目必须保留的业务能力

1. 只接受已切片 Bambu 3MF，并给未切片文件明确提示。
2. 安全解压 3MF，防 zip bomb、路径穿越和 XML entity 攻击。
3. 读取 plate、耗材、预测时间、重量和预览图。
4. 支持队列顺序、copies 和删除/移动。
5. 支持可编辑换盘 G-code 和提示音 G-code。
6. 支持旧版 `code.rar` 导入。
7. 支持多色通道自动映射和手动映射。
8. 导出前阻止同通道多颜色/多材料冲突。
9. 对 `M620`、`M621`、`Tn` 做安全通道重写。
10. 支持可选 A1 起始位置修正。
11. 支持可选 M73 盘号显示编码。
12. 插入换盘 G-code 时默认 fail fast，避免危险位置。
13. 更新 G-code md5、`slice_info.config`、`model_settings.config`、`_rels/.rels` 和 `filament_sequence.json`。
14. 输出后可交给 Bambu Connect。
15. 核心逻辑不依赖 GUI。
