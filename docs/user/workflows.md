# User Workflows

## 1. Basic Merge Workflow

1. User slices one or more plates in Bambu Studio or Orca Slicer.
2. User exports or saves a 3MF that contains `Metadata/plate_N.gcode`.
3. User opens ChangePlatAutoNext.
4. User imports one or more 3MF files.
5. App lists all printable plates.
6. User sets copies per plate and drags rows to adjust print order.
7. App auto-assigns actual AMS channels.
8. User reviews channel table.
9. User configures the G-code profile: per-plate before/after hooks, plate-change G-code, cooling, wait time, sound prompt, and optional M73 plate-number encoding.
10. User runs preflight validation.
11. User exports merged 3MF.
12. User optionally opens the result in Bambu Connect.

## 2. Multi-Color Workflow

1. Import plates that may each use local filament IDs.
2. App groups matching color/material/nozzle into actual channels.
3. User checks the actual loading table.
4. If conflict appears, user changes one local channel assignment.
5. App updates the conflict status live.
6. Export is allowed only when no blocking conflict remains.

## 3. Legacy Profile Import Workflow

1. User chooses old `net9.0-windows7.0` release directory.
2. App detects `code.rar`, `sound.rar`, and `set.ini`.
3. App decodes XOR + Base64 G-code snippets.
4. App maps supported `set.ini` options to the new profile format.
5. User reviews the imported profile.
6. App saves it as a normal JSON/text profile, not as encrypted `.rar`.

## 4. Unsliced 3MF Error Workflow

If a user imports a 3MF without `Metadata/plate_N.gcode`:

1. App rejects the file.
2. App explains that this is probably an unsliced project/model package.
3. App instructs the user to slice in Bambu Studio or Orca Slicer first.
4. App does not attempt to create G-code.

## 5. Export Preflight Workflow

Before writing output, app displays:

- Total printed plates.
- Total estimated time.
- Total material weight.
- Per-plate copies and print order.
- Actual AMS channel loading table.
- G-code profile name.
- Warnings.
- Blocking errors.

## 6. G-code Profile Workflow

1. User opens `G-code Profile`.
2. User optionally enters G-code that is prepended before every plate segment.
3. User edits the main plate-change G-code inserted near the finish-sound block.
4. User optionally enters G-code that is appended after every plate segment.
5. User edits the sound prompt snippet used while waiting.
6. User enables cooling before unloading if the bed should reach a target temperature first.
7. User enables waiting before the next plate and sets wait seconds.
8. User enables sound prompts during the wait and sets the loop count.
9. User optionally enables M73 plate-number encoding, which adds `6000 * plate_number` to `M73 R`.
10. User exports and validates the merged 3MF before real printing.

Export button is disabled if blocking errors exist.
