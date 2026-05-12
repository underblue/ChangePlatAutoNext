# Modern PyQt6 + QSS UI Design

本文档定义 ChangePlatAutoNext 桌面端的现代化界面方向。目标是比当前 PyQt6 原型更清晰、更稳定、更适合长时间操作，同时保持工程实现可控。

## 1. Design Goals

1. 使用 PyQt6 Widgets，不引入 WebView 前端栈。
2. 使用 QSS 统一视觉，不在业务代码里散写样式。
3. 主界面围绕“导入 -> 预检 -> 导出”的工作流，而不是把所有控件平铺。
4. 大文件导入导出必须有进度反馈和后台线程。
5. 安全状态必须可见：通道冲突、G-code 插入风险、未切片 3MF 等不能只靠弹窗。
6. 支持高 DPI，避免固定小字号和拥挤表格。
7. 先实现浅色专业主题，再预留深色主题接口。

## 2. Visual Direction

主题名称：`Fluent Light`

关键词：

- Windows 11 / Fluent 风格桌面软件。
- 浅色云母感背景。
- 圆角卡片和柔和边界。
- 蓝色主操作和 pill 状态标签。
- 左侧 NavigationView + 顶部 command bar。
- 接近现代生产工具，而不是系统默认 Qt 控件。

### 2.1 Palette

| Token | Value | Usage |
| --- | --- | --- |
| `--surface-0` | `#F4F1EA` | App background |
| `--surface-1` | `#FFFDF8` | Cards and panels |
| `--surface-2` | `#ECE7DC` | Secondary panels |
| `--ink-0` | `#1F2328` | Primary text |
| `--ink-1` | `#59636E` | Secondary text |
| `--border` | `#D8D0C1` | Dividers |
| `--accent` | `#126E82` | Primary action |
| `--accent-hover` | `#0F5C6D` | Primary hover |
| `--success` | `#287D3C` | Valid state |
| `--warning` | `#B7791F` | Warning state |
| `--danger` | `#B42318` | Blocking error |
| `--info` | `#3451B2` | Informational state |

### 2.2 Typography

Qt Widgets cannot reliably bundle web fonts without extra packaging work. Use platform-native UI fonts by default, but define a central font policy:

- macOS: `SF Pro Text` fallback through system font.
- Windows: `Segoe UI Variable` or `Segoe UI`.
- Linux: `Noto Sans`.
- Monospace editor: `JetBrains Mono`, `SF Mono`, `Consolas`, fallback monospace.

Do not hardcode fonts in every widget. Use `ThemeManager` to apply base `QFont` and QSS tokens.

## 3. Main Window Layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Top Bar: project title, import button, preflight status, export       │
├───────────────┬───────────────────────────────────────┬──────────────┤
│ Left Nav      │ Main Work Area                        │ Right Panel  │
│               │                                       │              │
│ 1 Queue       │ Queue table / channel table / editor  │ Preflight    │
│ 2 Channels    │ depending on selected nav item        │ Summary      │
│ 3 G-code      │                                       │ Warnings     │
│ 4 Export      │                                       │ Progress     │
├───────────────┴───────────────────────────────────────┴──────────────┤
│ Bottom Log: compact event stream                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.1 Top Bar

Contains:

- App name: `ChangePlatAutoNext`.
- Current workflow state: `No files`, `Ready`, `Warnings`, `Blocked`, `Exporting`.
- Primary buttons:
  - `Import 3MF`
  - `Run Preflight`
  - `Export 3MF`
  - `Open in Bambu Connect` after export

Rules:

- `Export 3MF` disabled when blocking errors exist.
- Primary action uses accent color.
- Destructive actions use text button plus confirmation, not red primary buttons.

### 3.2 Left Navigation

Use vertical navigation with clear sections:

1. `Queue`
2. `Channels`
3. `G-code Profile`
4. `Export`
5. `Settings`

This avoids overusing tabs and makes the workflow more deliberate.

### 3.3 Queue Page

Components:

- Drop zone card for `.3mf` files.
- Plate queue table.
- Plate preview strip.
- Per-row copies spin box bound to that plate entry.
- Drag handle / row drag behavior for changing print order.
- Move up/down actions.
- Remove action.

Table columns:

| Column | Meaning |
| --- | --- |
| Order | Queue order |
| Source | File name |
| Plate | Plate index |
| Copies | Per-row copies spinbox |
| Time | Prediction total |
| Weight | Weight total |
| Filaments | Compact color chips |
| Status | Valid/warning/error |

### 3.4 Channels Page

Two-panel layout:

- Upper panel: actual AMS channels.
- Lower panel: local filament assignment table.

Actual AMS channel table:

| Channel | Color | Material | Nozzle | Total g | Sources | State |
| --- | --- | --- | --- | --- | --- | --- |

Local assignment table:

| Queue | Plate | Local ID | Detected | Material | Used g | Assign to |
| --- | --- | --- | --- | --- | --- | --- |

Visual requirements:

- Use colored swatches for filament colors.
- Conflict rows use danger border and danger text.
- Empty channels shown in subdued style.
- The status panel explains exactly which channel conflicts and why.

### 3.5 G-code Profile Page

Components:

- Profile selector.
- Machine compatibility badge, e.g. `A1`, `A1 mini`, `Expert`.
- Before every plate G-code editor.
- Change G-code editor.
- After every plate G-code editor.
- Finish sound G-code editor.
- Cooling before unloading controls: enable flag and bed target temperature.
- Wait before next plate controls: enable flag and wait seconds.
- Sound prompt controls: enable flag and loop count.
- M73 plate-number encoding toggle.
- Diff/modified indicator.
- Import legacy snippet button.
- Restore default button.

Editor requirements:

- Use `QPlainTextEdit`.
- Use monospace font.
- Show line numbers if feasible in later iteration.
- Highlight high-risk profile changes as warning only, not as syntax validation unless parser is implemented.

### 3.6 Export Page

Components:

- Output path selector.
- Export summary.
- Metadata update summary.
- Progress bar.
- Export report link after success.

Preflight summary:

| Field | Example |
| --- | --- |
| Total plates | `5` |
| Estimated time | `12h 31m` |
| Material | `243.8 g` |
| AMS channels | `3` |
| Blocking errors | `0` |
| Warnings | `2` |

## 4. Component Architecture

```text
interfaces/desktop/
  app.py
  main_window.py
  theme.py
  workers.py
  view_models.py
  widgets/
    top_bar.py
    side_nav.py
    queue_page.py
    channels_page.py
    gcode_profile_page.py
    export_page.py
    log_panel.py
    status_badge.py
```

Rules:

- Widgets only render state and emit user intents.
- ViewModels own UI state and call application services.
- Workers execute long-running import/export tasks.
- ThemeManager loads QSS from resources.

## 5. QSS Strategy

QSS files live under:

```text
src/change_plate_next/interfaces/desktop/styles/
  workshop_light.qss
  workshop_dark.qss
```

Rules:

1. Use object names for special widgets, e.g. `#TopBar`, `#PrimaryButton`.
2. Use dynamic properties for states, e.g. `status="danger"`.
3. Avoid inline `setStyleSheet` except for dynamic color chips that cannot be represented cleanly by QSS.
4. Keep spacing and border radii consistent.
5. QSS must be loaded once by `ThemeManager`.

Dynamic property example:

```python
badge.setProperty("status", "danger")
badge.style().unpolish(badge)
badge.style().polish(badge)
```

QSS example:

```css
QLabel[status="danger"] {
  color: #B42318;
  background: #FEE4E2;
  border: 1px solid #FDA29B;
}
```

## 6. Interaction Rules

### 6.1 Import

- Import button opens file dialog.
- Drag-and-drop accepts `.3mf` only.
- Unsupported files show inline error and log entry.
- Import runs in background.

### 6.2 Preflight

Preflight runs automatically after:

- Queue change.
- Per-row copies change.
- Source table row order change.
- Channel mapping change.
- G-code profile change.
- Export path change.

Preflight result controls export button state.

### 6.3 Export

- Export runs in background.
- User can cancel before package writing reaches final atomic move.
- Progress events update page and bottom log.
- After success, user can open in Bambu Connect.

## 7. Accessibility

- Do not rely only on color for conflict state; include text labels.
- Minimum body font size should be 13px equivalent.
- Buttons need visible focus state.
- Tables should support row selection and keyboard navigation.
- Log and error messages should be copyable.

## 8. Implementation Milestones

### UI-M1: Theme Infrastructure

- Add `theme.py`.
- Add `workshop_light.qss`.
- Add test that QSS resource can be loaded.

### UI-M2: Static Shell

- Main window with top bar, side nav, placeholder pages.
- No business logic yet.

### UI-M3: Queue ViewModel

- Import result can populate queue table from fake data.
- Per-row copies updates state.
- Dragging source rows updates print order.

### UI-M4: Channels Page

- Actual channel table and local mapping table.
- Conflict state rendering.

### UI-M5: Background Workflow

- Import/export workers.
- Progress event display.

### UI-M6: Full Integration

- Real application workflow wired in.
- Export and Bambu Connect handoff.

## 9. Internationalization

The desktop UI supports three built-in languages:

- English: `en`
- French: `fr`
- Chinese: `zh`

Startup language is selected from the local system locale:

- `zh_CN`, `zh_TW`, `zh_HK` -> `zh`
- `fr_FR`, `fr_CA` -> `fr`
- any unsupported locale -> `en`

Implementation rules:

1. UI strings must use `Translator.text(key)` instead of hard-coded text.
2. New pages must add keys for all three languages.
3. Missing translations fall back to English, then to the key name.
4. A manual language selector can be added later in Settings without changing UI callers.
