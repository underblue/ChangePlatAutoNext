# Release Checklist

## Automated Checks

Run from repository root:

```bash
PYTHONPATH=src python -m pytest tests -q
python -m py_compile install.py packaging/pyinstaller_entry.py $(find src -name '*.py') $(find tests -name '*.py')
python install.py --clean
```

Expected test status for 1.0:

```text
24 passed, 3 skipped
```

The skipped tests are optional Qt widget instantiation tests. Run them manually with:

```bash
RUN_QT_GUI_TESTS=1 QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/unit/test_desktop_app.py -q
```

Expected optional desktop test status when PyQt6 and a compatible offscreen platform are available:

```text
3 passed
```

## Manual Desktop Verification

1. Launch the packaged app.
2. Confirm the app icon is visible.
3. Confirm language defaults to local system language.
4. Import one or more sliced 3MF files containing `Metadata/plate_N.gcode`.
5. Confirm source file table updates.
6. Confirm material channels table updates.
7. Open `G-code Profile` and confirm before/after plate editors, cooling, wait, sound, and M73 controls are visible.
8. Choose output path.
9. Export merged 3MF.
10. Confirm exported G-code contains the configured before/after hooks and plate-change behavior.
11. Open output in Bambu Connect.
12. Confirm Bambu Connect can read the file.

## Safety Verification

Before public distribution, validate with real representative files:

- Single plate, single material.
- Multiple sliced 3MF inputs, same material.
- Multiple sliced 3MF inputs, different material channels.
- Missing finish marker behavior.
- Unsliced 3MF rejection.

## Licensing

- Project license is `GPL-3.0-only` because PyQt6 open-source distribution is GPL v3.
- Closed-source commercial distribution requires appropriate PyQt commercial licensing.
- Include `LICENSE` in release archives.
