# Channel Mapping Contract

## 1. Problem

Every sliced plate has local filament IDs. These IDs are local to the plate and do not necessarily refer to the same physical AMS channel across plates.

Example:

```text
plate 1 local filament 1 = green PLA
plate 2 local filament 1 = red PLA
```

If the G-code is concatenated without remapping, both segments will use tool 0, causing the printer to use the same actual material channel for different colors.

## 2. Concepts

| Concept | Index Base | Example | Meaning |
| --- | --- | --- | --- |
| Local filament ID | 1-based | `filament id="1"` | ID from `slice_info.config` inside one plate |
| G-code tool index | 0-based | `T0`, `M620 S0A` | Tool number used by Bambu G-code |
| Actual AMS channel | 1-based | channel 3 | Physical/user-facing material slot |

Conversion:

```text
local filament id = gcode tool index + 1
gcode tool index = actual AMS channel - 1
```

## 3. Default Signature

Default auto-mapping groups filaments by:

```text
color.upper() + material.upper() + nozzle_diameter
```

Rationale:

- Color mismatch is visually wrong.
- Material mismatch is mechanically risky.
- Nozzle/profile mismatch may imply incompatible slicing assumptions.

## 4. Validation Rules

Blocking conflicts:

- Same actual channel maps to multiple colors.
- Same actual channel maps to multiple materials.
- Same actual channel maps to multiple nozzle diameters unless expert override is added later.

Warnings:

- Same channel has same signature but different `tray_info_idx`.
- Filament has missing color or material and fallback values are used.

## 5. G-code Rewrite Scope

Rewrite only:

- `M620 S<n>` variants.
- `M621 S<n>` variants.
- Standalone `T<n>` commands.

Do not rewrite:

- Comment lines.
- Unknown commands.
- Embedded templates in comments.
- Reserved tool numbers `255` and `1000`.

## 6. Acceptance Examples

Input mapping:

```python
{1: 3, 2: 4}
```

Expected rewrite:

```text
M620 S0A -> M620 S2A
M621 S1 A -> M621 S3 A
T0 -> T2
T255 -> T255
```
