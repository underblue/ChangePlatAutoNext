#!/usr/bin/env python3
"""Install dependencies and build a local executable with PyInstaller.

Usage:
    python install.py
    python install.py --skip-build
    python install.py --clean
    python install.py --run-tests

The script creates a project-local virtual environment, installs this project with the
runtime/desktop/image/build extras, and builds an executable for the current operating system.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
APP_NAME = "ChangePlatAutoNext"
ENTRY_SCRIPT = PROJECT_ROOT / "packaging" / "pyinstaller_entry.py"
ICON_FILE = PROJECT_ROOT / "packaging" / "assets" / "app_icon.icns"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install dependencies and build ChangePlatAutoNext.")
    parser.add_argument("--skip-build", action="store_true", help="Install dependencies only.")
    parser.add_argument("--clean", action="store_true", help="Remove build/dist/spec artifacts before building.")
    parser.add_argument("--onefile", action="store_true", help="Build a single-file executable instead of a folder app.")
    parser.add_argument("--with-test", action="store_true", help="Install test dependencies into the project virtual environment.")
    parser.add_argument("--run-tests", action="store_true", help="Install test dependencies and run the automated test suite before building.")
    parser.add_argument("--no-confirm", action="store_true", help="Run without interactive prompts.")
    return parser.parse_args()


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(command: list[str], *, cwd: Path = PROJECT_ROOT) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def ensure_supported_python() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required.")


def create_venv() -> None:
    if VENV_DIR.exists():
        print(f"Using existing virtual environment: {VENV_DIR}")
        return
    print(f"Creating virtual environment: {VENV_DIR}")
    venv.EnvBuilder(with_pip=True, clear=False).create(VENV_DIR)


def install_dependencies(*, include_test: bool = False) -> None:
    python = str(venv_python())
    run([python, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    extras = "desktop,image,build,test" if include_test else "desktop,image,build"
    run([python, "-m", "pip", "install", "-e", f".[{extras}]"])


def run_tests() -> None:
    python = str(venv_python())
    run([python, "-m", "pytest", "tests", "-q"])


def clean_artifacts() -> None:
    for path in [PROJECT_ROOT / "build", PROJECT_ROOT / "dist"]:
        if path.exists():
            print(f"Removing {path}")
            shutil.rmtree(path)
    spec_path = PROJECT_ROOT / f"{APP_NAME}.spec"
    if spec_path.exists():
        print(f"Removing {spec_path}")
        spec_path.unlink()


def pyinstaller_data_args() -> list[str]:
    separator = ";" if os.name == "nt" else ":"
    mappings = [
        (PROJECT_ROOT / "src" / "change_plate_next" / "interfaces" / "desktop" / "styles", "change_plate_next/interfaces/desktop/styles"),
        (PROJECT_ROOT / "src" / "change_plate_next" / "interfaces" / "desktop" / "assets", "change_plate_next/interfaces/desktop/assets"),
        (PROJECT_ROOT / "src" / "change_plate_next" / "resources", "change_plate_next/resources"),
    ]
    args: list[str] = []
    for source, target in mappings:
        args.extend(["--add-data", f"{source}{separator}{target}"])
    return args


def build_executable(onefile: bool) -> None:
    python = str(venv_python())
    command = [
        python,
        "-m",
        "PyInstaller",
        "--name",
        APP_NAME,
        "--windowed",
        "--clean",
        "--noconfirm",
        "--collect-all",
        "PyQt6",
    ]
    if ICON_FILE.exists():
        command.extend(["--icon", str(ICON_FILE)])
    command.extend(pyinstaller_data_args())
    if onefile:
        command.append("--onefile")
    command.append(str(ENTRY_SCRIPT))
    run(command)


def print_result(onefile: bool) -> None:
    system = platform.system()
    if system == "Darwin" and not onefile:
        output = PROJECT_ROOT / "dist" / f"{APP_NAME}.app"
    elif os.name == "nt":
        output = PROJECT_ROOT / "dist" / (f"{APP_NAME}.exe" if onefile else APP_NAME / f"{APP_NAME}.exe")
    else:
        output = PROJECT_ROOT / "dist" / (APP_NAME if onefile else APP_NAME / APP_NAME)
    print("\nBuild complete.")
    print(f"Output: {output}")
    print("\nLicense note: this PyQt6 build is intended for GPL-3.0-only distribution unless you have appropriate commercial PyQt licensing.")


def main() -> int:
    args = parse_args()
    ensure_supported_python()
    if args.clean:
        clean_artifacts()
    create_venv()
    install_dependencies(include_test=args.with_test or args.run_tests)
    if args.run_tests:
        run_tests()
    if not args.skip_build:
        build_executable(args.onefile)
        print_result(args.onefile)
    else:
        print("Dependencies installed. Build skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
