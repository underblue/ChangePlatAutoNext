# ChangePlatAutoNext

语言：简体中文 | [English](README.md)

ChangePlatAutoNext 是 ChangePlatAuto 的重构版本，用于处理已经由 Bambu Studio 或 Orca Slicer 切片后的 3MF 文件。它可以读取多个已切片 3MF 中的 plate G-code，合成为一个新的 3MF，并插入自动换盘相关 G-code。

这个项目包含桌面界面和命令行工具，适合需要把多个盘面按顺序合并、调整耗材通道、生成换盘流程并导出给 Bambu Connect 使用的场景。

## 适用输入

请使用已经切片完成的 Bambu/Orca 3MF 文件。输入文件通常需要包含：

- `Metadata/slice_info.config`
- `Metadata/plate_N.gcode`
- plate 元数据和预览资源

如果 3MF 只是模型工程文件，还没有 `plate_N.gcode`，请先在 Bambu Studio 或 Orca Slicer 中完成切片。

## 主要功能

- 导入一个或多个已切片 3MF。
- 读取 plate 预览、耗材、重量和预计时间。
- 调整打印顺序，并为每个 plate 设置份数。
- 映射本地耗材编号到实际 AMS 通道。
- 插入自动换盘 G-code、每盘前后附加 G-code、等待和提示音。
- 可选把当前盘号编码到 `M73 R` 剩余时间字段中显示。
- 导出合并后的 3MF。
- 可选通过 Bambu Connect 打开导出结果。

## 环境要求

- Python 3.11 或更新版本。
- 首次安装依赖时需要网络。
- 桌面界面依赖 PyQt6。

## 一键安装和打包

克隆项目后，在项目目录运行：

```bash
cd ChangePlatAutoNext
python install.py
```

脚本会自动创建 `.venv`，安装依赖，并使用 PyInstaller 打包当前系统可执行文件。输出位于 `dist/`。

常用选项：

```bash
python install.py --skip-build
python install.py --clean
python install.py --onefile
python install.py --run-tests
```

如果系统中 `python` 命令不可用，可以尝试：

```bash
python3 install.py
py install.py
```

## 运行桌面界面

如果已经执行过 `python install.py --skip-build` 或 `python install.py`，可以激活虚拟环境后运行：

macOS / Linux:

```bash
source .venv/bin/activate
change-plate-next-gui
```

Windows:

```bat
.venv\Scripts\activate
change-plate-next-gui
```

如果已经完成打包，也可以直接运行 `dist/` 中生成的应用或可执行文件。

## 命令行基础用法

查看 3MF 中的 plate 信息：

```bash
change-plate-next inspect input.3mf
```

输出 JSON：

```bash
change-plate-next inspect input.3mf --json
```

合并多个 3MF：

```bash
change-plate-next merge input1.3mf input2.3mf -o merged.3mf
```

指定换盘 G-code 片段：

```bash
change-plate-next merge input.3mf -o merged.3mf --change-gcode change_plate.gcode
```

更多 CLI 参数可以查看：

```bash
change-plate-next --help
change-plate-next merge --help
```

## 基本使用流程

1. 在 Bambu Studio 或 Orca Slicer 中完成切片并保存 3MF。
2. 打开 ChangePlatAutoNext。
3. 导入一个或多个 3MF 文件。
4. 检查 plate 列表、预览、耗材通道和打印顺序。
5. 设置每个 plate 的份数和换盘 G-code 配置。
6. 导出合并后的 3MF。
7. 真实打印前，在切片软件或打印流程中再次检查运动命令和换盘位置。

## 安全提醒

G-code 会直接影响打印机运动。真实打印前请务必检查导出的 G-code，尤其是归零、移动、退盘、热床等待和换盘相关命令。本工具不会直接启动打印任务，也不会保存 Bambu 账号凭据。

## 许可证

本项目使用 `GPL-3.0-only` 许可证。桌面应用使用 PyQt6，开源发布按 GPL v3 约束进行。更多背景请阅读 [docs/license_policy.md](docs/license_policy.md)。

完整架构、开发文档和实现细节请阅读 [英文 README](README.md) 以及 `docs/` 目录。
