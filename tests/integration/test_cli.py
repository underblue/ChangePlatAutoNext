import json
import zipfile

from change_plate_next.interfaces.cli.main import default_change_gcode, main
from tests.fixtures.build_3mf import write_synthetic_3mf


def test_cli_inspect_json(tmp_path, capsys) -> None:
    source = write_synthetic_3mf(tmp_path / "input.3mf", colors=("#00FF00",))
    assert main(["inspect", str(source), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["plate"] == 1


def test_cli_merge(tmp_path) -> None:
    source = write_synthetic_3mf(tmp_path / "input.3mf")
    output = tmp_path / "out.3mf"
    assert main(["merge", str(source), "--output", str(output), "--no-start-fix"]) == 0
    with zipfile.ZipFile(output, "r") as zf:
        assert "Metadata/plate_1.gcode" in zf.namelist()
        text = zf.read("Metadata/plate_1.gcode").decode("utf-8")
    assert "G28 Y" in text
    assert "G380 S2 Y264 F2000" in text
    assert "G1 Z30 F600" in text


def test_cli_default_change_gcode_uses_legacy_sequence() -> None:
    text = default_change_gcode()
    assert text.startswith(";start change plate")
    assert "G28 Y" in text
    assert "G380 S2 Z95" in text
    assert "G1 Y-2 F20000" in text
    assert text.strip().endswith(";end change plate")


def test_cli_merge_with_full_gcode_profile(tmp_path) -> None:
    source = write_synthetic_3mf(tmp_path / "input.3mf", colors=("#00FF00",))
    output = tmp_path / "out.3mf"
    change = tmp_path / "change.gcode"
    sound = tmp_path / "sound.gcode"
    pre = tmp_path / "pre.gcode"
    post = tmp_path / "post.gcode"
    change.write_text(";start change plate\nM400\n;end change plate\n", encoding="utf-8")
    sound.write_text(";sound tip\nM1006 W\n", encoding="utf-8")
    pre.write_text(";pre hook\n", encoding="utf-8")
    post.write_text(";post hook\n", encoding="utf-8")
    assert (
        main(
            [
                "merge",
                str(source),
                "--output",
                str(output),
                "--change-gcode",
                str(change),
                "--sound-gcode",
                str(sound),
                "--pre-plate-gcode",
                str(pre),
                "--post-plate-gcode",
                str(post),
                "--m73-plate-number",
                "--wait-hotbed-cool",
                "--hotbed-temp",
                "44",
                "--wait-before-next-plate",
                "--wait-seconds",
                "8",
                "--sound-tip-when-waiting",
                "--sound-tip-count",
                "2",
            ]
        )
        == 0
    )
    with zipfile.ZipFile(output, "r") as zf:
        text = zf.read("Metadata/plate_1.gcode").decode("utf-8")
    assert text.startswith(";pre hook\n")
    assert "M73 P1 R6005" in text
    assert "M190 S44\n;start change plate" in text
    assert text.count(";sound tip") == 2
    assert text.count("G4 P4000") == 2
    assert text.endswith(";post hook\n")
