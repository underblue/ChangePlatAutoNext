# Changelog

All notable changes to ChangePlatAutoNext will be documented in this file.

## 1.0.0 - 2026-05-12

### Added

- Initial clean-architecture scaffold.
- Detailed current-project understanding document.
- Detailed architecture design document.
- VibeCoding-oriented implementation guides.

### Added

- Working core implementation for 3MF inspect/export workflow.
- G-code transformation pipeline.
- Safe archive and XML adapters.
- CLI inspect and merge commands.
- Synthetic 3MF integration tests.
- PyQt6/QSS desktop shell and PyInstaller build entry.

### Tests

- Added unit and integration tests covering channel mapping, G-code transforms, archive safety, CLI, and end-to-end synthetic export.

### Release Notes

- Desktop app is now usable for importing sliced 3MF files, composing a single merged output, editing plate-change G-code options, exporting, and opening the result in Bambu Connect.
- CLI supports `inspect` and `merge`.
- Automated tests cover core import/export behavior with synthetic 3MF packages.
