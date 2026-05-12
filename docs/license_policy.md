# License Policy

## Decision

ChangePlatAutoNext is licensed as `GPL-3.0-only`.

## Reason

The desktop interface is explicitly based on PyQt6. PyQt6 is dual licensed under GNU GPL v3 and the Riverbank Commercial License. Riverbank states that PyQt is not available under LGPL. Therefore, an open-source PyQt6-based desktop application should use a GPL-compatible license.

## Practical Meaning

For open-source distribution:

- Use `GPL-3.0-only` for this project.
- Keep source code available when distributing the application.
- Preserve license notices.
- Include the GPL notice in the About dialog.

For proprietary/commercial closed-source distribution:

- Do not rely on the GPL PyQt6 package.
- Obtain the appropriate Riverbank Commercial License for PyQt.
- Confirm Qt licensing obligations for the Qt components distributed with the application.
- Re-check all third-party dependencies before packaging.

## References

- Riverbank PyQt licensing page: https://riverbankcomputing.com/software/pyqt
- Riverbank commercial license FAQ: https://www.riverbankcomputing.com/commercial/license-faq
- PyQt6 PyPI project metadata: https://pypi.org/project/PyQt6/
- GNU GPL v3 text: https://www.gnu.org/licenses/gpl-3.0.txt
