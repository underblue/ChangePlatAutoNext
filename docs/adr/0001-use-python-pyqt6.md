# ADR 0001: Use Python and PyQt6

## Status

Accepted.

## Context

The current project already contains a Python implementation of the core 3MF/G-code workflow and a PyQt6 GUI. The older .NET directory appears to be a release artifact, not a maintainable source tree.

## Decision

The redesigned project will use Python for the core application and PyQt6 for the desktop UI.

## Consequences

- Core logic can be tested with normal Python unit tests.
- GUI remains cross-platform enough for development.
- Packaging remains simpler than reverse-engineering the old .NET binary.
- Performance is acceptable because the workload is mostly ZIP, XML, text, and small image processing.

## License Impact

Because the open-source PyQt6 package is GPL v3, this project uses `GPL-3.0-only`. Closed-source commercial distribution requires the appropriate PyQt commercial license and dependency review.
