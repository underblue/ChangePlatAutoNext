# VibeCoding Agent Playbook

本文档面向使用 AI 编程助手逐步实现 ChangePlatAutoNext 的场景。目标是让每次对话都能落在一个小而可验证的任务上，而不是让 Agent 一次性生成不可审查的大坨代码。

## 1. 总原则

1. 每次只做一个清晰任务。
2. 每个任务必须有明确文件边界。
3. 每个任务必须有验收命令或验收测试。
4. 不允许为了跑通示例而绕开安全边界。
5. 不允许把 GUI 逻辑写进 domain 或 application。
6. 不允许把 ZIP/XML/G-code 细节散落在 UI 层。
7. 不允许提交虚拟环境、缓存、私有模型文件、大型二进制样例。
8. 如果行为涉及 G-code 运动安全，必须默认 fail-fast，并在文档里解释风险。

## 2. 推荐对话模板

### 2.1 新任务模板

```text
请按 ChangePlatAutoNext/docs/vibecoding/agent_playbook.md 工作。
任务：实现 ArchiveGuard。
范围：只修改 src/change_plate_next/adapters/bambu_3mf/archive_guard.py 和 tests/unit/test_archive_guard.py。
要求：实现路径穿越、反斜杠、symlink、文件数、单文件大小、总大小、压缩比、CRC 检查。
验收：python -m pytest tests/unit/test_archive_guard.py
```

### 2.2 Bug 修复模板

```text
请修复以下失败测试，不要扩大范围：
命令：python -m pytest tests/integration/test_export_synthetic_3mf.py
错误：...
允许修改：metadata_rewriter.py、test fixture builder。
完成后说明根因和改动。
```

### 2.3 设计变更模板

```text
我要修改通道映射规则，把 nozzle_diameter 纳入默认 signature。
请先更新 docs/api/channel_mapping_contract.md，再改代码和测试。
不要改 GUI。
```

## 3. Agent 工作流程

每个任务按固定流程执行：

1. 读取相关文档和目标文件。
2. 给出 3 到 6 步简短计划。
3. 实现最小改动。
4. 添加或更新测试。
5. 运行指定测试。
6. 如果测试失败，修复直到通过或说明阻塞。
7. 最终总结改动文件、验证命令、剩余风险。

## 4. 文件所有权规则

### 4.1 Domain 任务

允许修改：

- `src/change_plate_next/domain/`
- `tests/unit/test_*domain*.py`
- `docs/api/*.md`

禁止修改：

- `interfaces/desktop/`
- `adapters/bambu_3mf/`
- `adapters/connect/`

### 4.2 G-code 任务

允许修改：

- `src/change_plate_next/adapters/gcode/`
- `tests/unit/test_gcode_*.py`
- `tests/fixtures/gcode/`

注意事项：

- 只能重写白名单命令。
- 注释行必须保持原样。
- 未知命令必须保持原样。
- 插入策略必须有 fail-fast 测试。

### 4.3 3MF Adapter 任务

允许修改：

- `src/change_plate_next/adapters/bambu_3mf/`
- `tests/unit/test_archive_guard.py`
- `tests/integration/test_*3mf*.py`
- `tests/fixtures/3mf/`

注意事项：

- 不允许使用不安全解压。
- 不允许直接信任包内路径。
- XML 解析必须通过统一 SafeXml 组件。

### 4.4 Application 任务

允许修改：

- `src/change_plate_next/application/`
- `src/change_plate_next/ports/`
- `tests/unit/test_merge_planner.py`
- `tests/integration/test_export_workflow.py`

注意事项：

- Application 只编排，不直接解析 XML 或调用 PyQt。
- Use case 错误必须转成领域错误或应用错误，不泄露底层 traceback 给普通用户。

### 4.5 GUI 任务

允许修改：

- `src/change_plate_next/interfaces/desktop/`
- `tests/unit/test_view_models.py`

注意事项：

- GUI 不能直接读写 3MF。
- GUI 不能阻塞主线程执行导入/导出。
- 所有状态变化通过 ViewModel 或 application workflow。

## 5. 验收标准

每个实现任务至少满足：

1. 有测试覆盖新增或改变的行为。
2. 指定测试命令通过。
3. 没有引入跨层依赖。
4. 没有生成物进入源码目录。
5. 错误信息对用户可操作。
6. 对安全敏感行为有 fail-fast 或显式确认路径。

## 6. 常见反模式

| 反模式 | 为什么不接受 | 应改为 |
| --- | --- | --- |
| 在 GUI slot 里解析 3MF | 无法测试，UI 阻塞 | 调用 application workflow |
| 在 domain model 里放 Path 解包逻辑 | domain 污染 IO | adapter 解析后生成 domain 对象 |
| 一次性写完整导出流程 | 难审查，难定位 bug | ArchiveGuard、MetadataReader、GcodePipeline、PackageWriter 分任务实现 |
| 找不到结束标记就直接追加换盘 G-code | 可能造成危险运动 | 默认 fail-fast，风险策略必须显式选择 |
| 用真实大 3MF 做唯一测试 | 慢且不可公开 | synthetic fixtures + 少量手动验收样例 |
| 把旧版 .NET 发布物复制进新项目 | 增加噪声和体积 | 只保留兼容解析器和小 fixture |

## 7. 推荐实现顺序

1. Domain models and errors。
2. Channel mapping service。
3. Legacy crypto reader。
4. G-code parser and transform stages。
5. ArchiveGuard。
6. SafeXmlStore。
7. MetadataReader。
8. MergePlanner。
9. MetadataRewriter。
10. PackageWriter。
11. CLI inspect。
12. CLI merge。
13. Desktop ViewModels。
14. Desktop UI。
15. Bambu Connect launcher。

## 8. 每次提交说明格式

```text
Summary:
- Implemented ArchiveGuard safety checks.
- Added unit tests for path traversal and zip bomb limits.

Validation:
- python -m pytest tests/unit/test_archive_guard.py

Notes:
- CRC failure test uses an intentionally corrupted zip fixture builder.
```
