# 迁移计划

## 阶段 1: 固化旧行为

1. 修复旧项目测试中的 `ET` 未定义问题，或在新项目测试中复现并防回归。
2. 把当前 synthetic 3MF 测试迁移到新项目 fixtures。
3. 增加 G-code golden tests，覆盖通道重映射和换盘插入。
4. 整理默认 G-code 片段为资源文件。

## 阶段 2: 抽出核心域

1. 迁移 `FilamentInfo`、`PlateInfo`、`QueueItem` 到新 domain model。
2. 把 `auto_assign_channels`、`validate_channel_assignments`、`aggregate_filaments` 改为 domain service。
3. 引入 `MergePlan`，让导出前可完整预检。

## 阶段 3: 重写 Adapter

1. 实现 `ArchiveGuard`。
2. 实现 `MetadataReader` 和 `MetadataRewriter`。
3. 实现 `GcodePipeline`。
4. 实现 `PackageWriter`。
5. 用 fixtures 验证导出 3MF 内部一致性。

## 阶段 4: 新 UI 和 CLI

1. 先实现 CLI，快速验证核心用例。
2. 重建 PyQt6 GUI，用后台 worker 调用 application workflow。
3. 加入导出预检面板和导出报告。
4. 加入 Bambu Connect handoff。

## 阶段 5: 兼容和清理

1. 实现旧版 `code.rar`/`sound.rar` 导入。
2. 可选实现 `set.ini` 迁移器。
3. 移除源码树中的虚拟环境和二进制发布物，或至少加入 `.gitignore`/发布说明。
4. 编写用户使用文档。
