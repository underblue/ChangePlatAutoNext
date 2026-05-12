# Install and Build

本文档说明用户 clone 项目后如何安装依赖并打包当前系统可执行文件。

## 1. Requirements

- Python 3.11 or newer.
- Internet access for first-time dependency installation.
- A normal local Python installation, not only an embedded/minimal Python.

Platform notes:

- Windows: run from PowerShell or CMD.
- macOS: run from Terminal. The generated `.app` may need Gatekeeper approval if distributed outside the local machine.
- Linux: Qt platform packages may be required by the distribution if PyQt6 cannot find a platform plugin.

## 2. One-Command Install and Build

From the cloned repository:

```bash
cd ChangePlatAutoNext
python install.py
```

The script will:

1. Create `.venv` inside the project.
2. Upgrade `pip`, `setuptools`, and `wheel`.
3. Install this project with `desktop`, `image`, and `build` extras.
4. Run PyInstaller.
5. Write output to `dist/`.

## 3. Useful Options

Install dependencies only:

```bash
python install.py --skip-build
```

Clean previous build artifacts and rebuild:

```bash
python install.py --clean
```

Build a single-file executable:

```bash
python install.py --onefile
```

Install test dependencies and run the automated suite before packaging:

```bash
python install.py --run-tests
```

## 4. Expected Output

macOS folder build:

```text
dist/ChangePlatAutoNext.app
```

Windows folder build:

```text
dist/ChangePlatAutoNext/ChangePlatAutoNext.exe
```

Linux folder build:

```text
dist/ChangePlatAutoNext/ChangePlatAutoNext
```

Single-file output is written directly under `dist/`.

## 5. License Note

The packaged desktop app uses PyQt6. The open-source PyQt6 package is GPL v3, so the generated executable is intended for GPL-3.0-only distribution unless the distributor has appropriate commercial PyQt licensing.

See `docs/license_policy.md`.

## 6. Troubleshooting

### Python command not found

Try one of:

```bash
python3 install.py
py install.py
```

### PyInstaller cannot find Qt plugins

Run:

```bash
python install.py --clean
```

If the problem persists, inspect the PyInstaller log and confirm PyQt6 installed correctly inside `.venv`.

### Network installation fails

Install dependencies manually once network access is available:

```bash
python -m pip install -r requirements/build.txt
```

Then rerun:

```bash
python install.py
```

### App launches but layout looks stale

Rebuild from a clean tree so PyInstaller refreshes bundled QSS and Python modules:

```bash
python install.py --clean
```
