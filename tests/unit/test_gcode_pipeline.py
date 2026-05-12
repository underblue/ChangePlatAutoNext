import pytest

from change_plate_next.adapters.gcode.pipeline import GcodePipeline
from change_plate_next.adapters.gcode.stages import GcodeContext
from change_plate_next.domain.errors import FinishMarkerMissingError
from change_plate_next.domain.models import AmsChannel, LocalFilamentId, PlateChangeRecipe
from change_plate_next.domain.policies import InsertionStrategy

MARKER = ";=====printer finish  sound========="


def test_pipeline_remaps_and_inserts_change_gcode() -> None:
    source = f"G0 Y254 F3000\n; M620 S0A comment\nM620 S0A   ; switch\nT0\nM73 P1 R5\n{MARKER}\nM1006\n{MARKER}\n"
    recipe = PlateChangeRecipe(
        change_gcode=";start change plate\nM400\n;end change plate\n",
        encode_plate_number_in_m73=True,
    )
    result = GcodePipeline().run(source, GcodeContext({LocalFilamentId(1): AmsChannel(3)}, 2, recipe))
    assert "; M620 S0A comment" in result.text
    assert "M620 S2A   ; switch" in result.text
    assert "T2" in result.text
    assert "M73 P1 R12005" in result.text
    assert ";start change plate" in result.text
    assert "G0 Y250 F3000 ;XKY ADD" in result.text


def test_pipeline_applies_plate_hooks_wait_cooldown_and_sound() -> None:
    source = f"G0 Y254 F3000\nM73 P1 R5\n{MARKER}\nM1006\n{MARKER}\n"
    recipe = PlateChangeRecipe(
        pre_plate_gcode=";before plate\nM400\n",
        post_plate_gcode=";after plate\nM400\n",
        change_gcode=";start change plate\nM400\n;end change plate\n",
        sound_gcode=";beep\nM1006 W\n",
        wait_hotbed_cool=True,
        hotbed_temp=35,
        wait_before_next_plate=True,
        wait_seconds=10,
        sound_tip_when_waiting=True,
        sound_tip_count=2,
        encode_plate_number_in_m73=True,
    )
    result = GcodePipeline().run(source, GcodeContext(plate_number=3, recipe=recipe))
    assert result.text.startswith(";before plate\nM400\n")
    assert "M73 P1 R18005" in result.text
    assert "M190 S40\n;start change plate" in result.text
    assert result.text.count(";beep") == 2
    assert result.text.count("G4 P5000") == 2
    assert result.text.endswith(";after plate\nM400\n")
    assert result.metrics["pre_plate_insertions"] == 1
    assert result.metrics["post_plate_insertions"] == 1


def test_pipeline_waits_without_sound_when_requested() -> None:
    recipe = PlateChangeRecipe(
        change_gcode=";start change plate\nM400\n;end change plate\n",
        wait_before_next_plate=True,
        wait_seconds=7,
    )
    result = GcodePipeline().run(f"G1 X1\n{MARKER}\nM1006\n{MARKER}\n", GcodeContext(recipe=recipe))
    assert "G4 P7000" in result.text
    assert result.text.count("G4 P7000") == 1


def test_missing_marker_fails_by_default() -> None:
    recipe = PlateChangeRecipe(change_gcode=";start change plate\nM400\n;end change plate\n")
    with pytest.raises(FinishMarkerMissingError):
        GcodePipeline().run("G1 X1\n", GcodeContext(recipe=recipe))


def test_append_strategy_warns() -> None:
    recipe = PlateChangeRecipe(
        change_gcode=";start change plate\nM400\n;end change plate\n",
        insertion_strategy=InsertionStrategy.APPEND_WITH_WARNING,
    )
    result = GcodePipeline().run("G1 X1\n", GcodeContext(recipe=recipe))
    assert result.warnings
    assert result.text.endswith(";end change plate\n")
