import zipfile

from change_plate_next.application.workflow import ChangePlateWorkflow
from change_plate_next.domain.models import PlateChangeRecipe
from tests.fixtures.build_3mf import write_synthetic_3mf, write_unsliced_3mf


def test_workflow_exports_synthetic_3mf(tmp_path) -> None:
    source = write_synthetic_3mf(tmp_path / "input.3mf")
    output = tmp_path / "merged.3mf"
    workflow = ChangePlateWorkflow.create_default()
    queue = workflow.build_queue_from_packages([source])
    result = workflow.export_queue(
        queue,
        PlateChangeRecipe(change_gcode=";start change plate\nM400\n;end change plate\n", apply_start_position_fix=True),
        output,
    )
    assert result.total_printed_plates == 2
    with zipfile.ZipFile(output, "r") as zf:
        names = set(zf.namelist())
        assert "Metadata/plate_1.gcode" in names
        assert "Metadata/plate_1.gcode.md5" in names
        assert "Metadata/plate_2.gcode" not in names
        merged = zf.read("Metadata/plate_1.gcode").decode("utf-8")
        assert "M620 S0A" in merged
        assert "M620 S1A" in merged
        assert ";start change plate" in merged
        slice_info = zf.read("Metadata/slice_info.config").decode("utf-8")
        assert 'value="3.00"' in slice_info


def test_single_plate_export_still_appends_change_gcode(tmp_path) -> None:
    source = write_synthetic_3mf(tmp_path / "single.3mf", colors=("#00FF00",))
    output = tmp_path / "single-merged.3mf"
    workflow = ChangePlateWorkflow.create_default()
    queue = workflow.build_queue_from_packages([source])
    result = workflow.export_queue(
        queue,
        PlateChangeRecipe(change_gcode=";start change plate\nM400\n;end change plate\n"),
        output,
    )
    assert result.total_printed_plates == 1
    with zipfile.ZipFile(output, "r") as zf:
        merged = zf.read("Metadata/plate_1.gcode").decode("utf-8")
        assert merged.count(";start change plate") == 1
        assert merged.index(";start change plate") < merged.index(";=====printer finish  sound=========")


def test_export_applies_full_gcode_profile(tmp_path) -> None:
    source = write_synthetic_3mf(tmp_path / "profile.3mf", colors=("#00FF00",))
    output = tmp_path / "profile-merged.3mf"
    workflow = ChangePlateWorkflow.create_default()
    queue = workflow.build_queue_from_packages([source])
    result = workflow.export_queue(
        queue,
        PlateChangeRecipe(
            pre_plate_gcode=";pre plate\nM400\n",
            post_plate_gcode=";post plate\nM400\n",
            change_gcode=";start change plate\nM400\n;end change plate\n",
            sound_gcode=";sound tip\nM1006 W\n",
            wait_hotbed_cool=True,
            hotbed_temp=45,
            wait_before_next_plate=True,
            wait_seconds=12,
            sound_tip_when_waiting=True,
            sound_tip_count=3,
            encode_plate_number_in_m73=True,
        ),
        output,
    )
    assert result.total_printed_plates == 1
    with zipfile.ZipFile(output, "r") as zf:
        merged = zf.read("Metadata/plate_1.gcode").decode("utf-8")
        assert merged.startswith(";pre plate\nM400\n")
        assert "M73 P1 R6005" in merged
        assert "M190 S45\n;start change plate" in merged
        assert merged.count(";sound tip") == 3
        assert merged.count("G4 P4000") == 3
        assert merged.endswith(";post plate\nM400\n")


def test_export_respects_queue_order_and_per_entry_copies(tmp_path) -> None:
    source = write_synthetic_3mf(tmp_path / "order.3mf", colors=("#00FF00", "#FF0000"))
    output = tmp_path / "order-merged.3mf"
    workflow = ChangePlateWorkflow.create_default()
    queue = workflow.build_queue_from_packages([source])
    queue = [queue[1], queue[0]]
    queue[0].copies = 2
    queue[1].copies = 1
    result = workflow.export_queue(
        queue,
        PlateChangeRecipe(change_gcode=";start change plate\nM400\n;end change plate\n", apply_start_position_fix=False),
        output,
    )
    assert result.total_printed_plates == 3
    with zipfile.ZipFile(output, "r") as zf:
        merged = zf.read(f"Metadata/plate_{result.target_plate_index}.gcode").decode("utf-8")
        first = merged.index("G1 X2")
        second = merged.index("G1 X2", first + 1)
        third = merged.index("G1 X1")
        assert first < second < third
        assert merged.count(";start change plate") == 3


def test_export_merges_multiple_imported_packages_into_one_queue(tmp_path) -> None:
    first_source = write_synthetic_3mf(tmp_path / "first.3mf", colors=("#00FF00",))
    second_source = write_synthetic_3mf(tmp_path / "second.3mf", colors=("#FF0000",))
    output = tmp_path / "merged-multi-source.3mf"
    workflow = ChangePlateWorkflow.create_default()
    queue: list = []
    queue.extend(workflow.build_queue_from_packages([first_source], copies=1, auto_map=False))
    queue.extend(workflow.build_queue_from_packages([second_source], copies=1, auto_map=False))
    from change_plate_next.domain.channel_mapping import auto_assign_channels

    auto_assign_channels(queue)
    result = workflow.export_queue(
        queue,
        PlateChangeRecipe(change_gcode=";start change plate\nM400\n;end change plate\n", apply_start_position_fix=False),
        output,
    )
    assert result.total_printed_plates == 2
    with zipfile.ZipFile(output, "r") as zf:
        merged = zf.read(f"Metadata/plate_{result.target_plate_index}.gcode").decode("utf-8")
        first = merged.index("G1 X1")
        second = merged.index("G1 X1", first + 1)
        assert first < second
        assert merged.count(";start change plate") == 2


def test_unsliced_3mf_has_actionable_error(tmp_path) -> None:
    source = write_unsliced_3mf(tmp_path / "unsliced.3mf")
    workflow = ChangePlateWorkflow.create_default()
    try:
        workflow.inspect_package(source)
    except Exception as exc:
        message = str(exc)
    else:
        raise AssertionError("expected error")
    assert "未切片" in message
