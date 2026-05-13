import os
import sys
from pathlib import Path

import pytest

if os.environ.get("RUN_QT_GUI_TESTS") != "1":
    pytest.skip(
        "Qt widget tests are opt-in because headless runners can lack Qt system libraries.",
        allow_module_level=True,
    )

from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from change_plate_next.domain.models import FilamentSignature, FilamentUsage, LocalFilamentId, Plate, PlateAssetRefs, PlateId, QueueEntry  # noqa: E402
from change_plate_next.interfaces.desktop.app import MainWindow, StepperSpinBox  # noqa: E402
from change_plate_next.interfaces.desktop.i18n import Translator  # noqa: E402
from change_plate_next.interfaces.desktop.settings_store import load_settings  # noqa: E402


def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def plate(name: str, *, index: int, weight: float = 2.0) -> Plate:
    filament = FilamentUsage(LocalFilamentId(1), "tray", FilamentSignature("#00FF00", "PLA", "0.40"), used_g=weight)
    return Plate(
        PlateId(name),
        Path(f"{name}.3mf"),
        Path("root"),
        index,
        name,
        PlateAssetRefs(Path(f"plate_{index}.gcode")),
        prediction_seconds=60,
        weight_g=weight,
        filaments=(filament,),
    )


def test_main_window_initializes_in_chinese() -> None:
    qapp()
    window = MainWindow(Translator("zh"))
    assert window.import_button.text() == "导入 3MF"
    assert window.settings_language_label.text() == "语言"
    assert window.nav_buttons[0].text() == "合成 3MF"
    assert window.page_stack.currentIndex() == 0
    assert window.page_title_label.text() == "合成 3MF"
    assert window.sources_table.columnCount() == 7
    assert window.sources_table.horizontalHeaderItem(0).text() == "顺序"
    assert window.sources_table.horizontalHeaderItem(1).text() == "预览"
    assert window.sources_table.horizontalHeaderItem(2).text() == "模型"
    assert window.sources_title.text() == "打印项"
    assert "G28 Y" in window.change_editor.toPlainText()
    assert "G380 S2 Y264 F2000" in window.change_editor.toPlainText()


def test_navigation_buttons_switch_pages() -> None:
    qapp()
    window = MainWindow(Translator("zh"))
    window.nav_buttons[1].click()
    assert window.page_stack.currentIndex() == 1
    assert window.page_title_label.text() == "耗材通道"
    assert window.nav_buttons[1].property("active") == "true"
    assert window.nav_buttons[0].property("active") == "false"

    window.nav_buttons[2].click()
    assert window.page_stack.currentIndex() == 2
    assert window.page_title_label.text() == "G-code 配置"
    assert window.advanced_toggle.text() == "高级设置"
    assert not window.advanced_container.isVisible()
    assert window.pre_plate_title.text() == "每盘打印前 G-code"
    assert window.post_plate_title.text() == "每盘打印后 G-code"
    assert window.sound_gcode_title.text() == "提示音 G-code"
    assert window.cooldown_check.text() == "退盘前等待热床冷却到目标温度"
    assert window.m73_check.text() == "剩余时间百位显示盘号"
    assert window.wait_seconds_spin.value() == 120
    assert window.sound_tip_count_spin.value() == 10
    assert isinstance(window.wait_seconds_spin, StepperSpinBox)

    window.advanced_toggle.click()
    assert window.advanced_container.isVisible()


def test_source_table_binds_copies_to_each_row_and_reorders_queue() -> None:
    qapp()
    window = MainWindow(Translator("zh"))
    window.queue = [
        QueueEntry(plate("first", index=1), copies=1),
        QueueEntry(plate("second", index=2), copies=2),
        QueueEntry(plate("third", index=3), copies=3),
    ]
    window.source_paths = [item.plate.source_package for item in window.queue]
    window._refresh_state()

    assert window.sources_table.rowCount() == 3
    assert window.sources_value.text() == "3"
    assert window.sources_hint.text() == "拖动打印项行可调整打印顺序。"
    assert isinstance(window.sources_table.cellWidget(0, 1), QLabel)
    assert window.sources_table.item(0, 0).text() == "#1"
    assert window.sources_table.item(1, 0).text() == "#2"
    spin = window.sources_table.cellWidget(1, 3)
    assert isinstance(spin, StepperSpinBox)
    spin.setValue(5)
    window.update_row_copies(1, spin.value())
    assert window.queue[1].copies == 5
    assert window.queue[0].copies == 1

    window.move_queue_row(2, 0)
    assert [item.plate.display_name for item in window.queue] == ["third", "first", "second"]
    assert window.queue[2].copies == 5
    assert window.sources_table.item(0, 0).text() == "#1"
    assert "third" in window.sources_table.item(0, 2).text()
    assert window.sources_table.item(0, 6).text() == "third.3mf"


def test_language_switch_updates_labels() -> None:
    qapp()
    window = MainWindow(Translator("en"))
    window.nav_buttons[4].click()
    window.language_combo.setCurrentIndex(window.language_combo.findData("fr"))
    assert window.import_button.text() == "Importer 3MF"
    assert window.nav_buttons[0].text() == "Fusionner"
    assert window.page_stack.currentIndex() == 4
    assert window.page_title_label.text() == "Paramètres"
    assert window.settings_language_label.text() == "Langue"


def test_queue_accumulates_imported_items_and_can_be_cleared() -> None:
    qapp()
    window = MainWindow(Translator("zh"))
    first_batch = [QueueEntry(plate("alpha", index=1), copies=1)]
    second_batch = [QueueEntry(plate("beta", index=2), copies=1), QueueEntry(plate("gamma", index=3), copies=2)]

    window.source_paths.extend([item.plate.source_package for item in first_batch])
    window.queue.extend(first_batch)
    window._refresh_state()

    window.source_paths.extend([item.plate.source_package for item in second_batch])
    window.queue.extend(second_batch)
    window._refresh_state()

    assert window.sources_value.text() == "3"
    assert window.sources_table.rowCount() == 3
    assert [item.plate.display_name for item in window.queue] == ["alpha", "beta", "gamma"]

    window.clear_queue()
    assert window.sources_value.text() == "0"
    assert window.sources_table.rowCount() == 0
    assert window.queue == []
    assert window.source_paths == []


def test_gcode_settings_are_persisted(tmp_path, monkeypatch) -> None:
    qapp()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    window = MainWindow(Translator("zh"))
    window.output_directory = tmp_path / "exports"
    window.change_editor.setPlainText(";persisted change\nM400\n")
    window.pre_plate_editor.setPlainText(";pre\n")
    window.post_plate_editor.setPlainText(";post\n")
    window.language_combo.setCurrentIndex(window.language_combo.findData("fr"))
    window.m73_check.setChecked(True)
    window.wait_seconds_spin.setValue(321)
    window._persist_settings()

    saved = load_settings()
    assert saved.change_gcode == ";persisted change\nM400\n"
    assert saved.pre_plate_gcode == ";pre\n"
    assert saved.post_plate_gcode == ";post\n"
    assert saved.language == "fr"
    assert saved.output_directory == str(tmp_path / "exports")
    assert saved.encode_plate_number_in_m73 is True
    assert saved.wait_seconds == 321

    reloaded = MainWindow()
    assert reloaded.change_editor.toPlainText() == ";persisted change\nM400\n"
    assert reloaded.pre_plate_editor.toPlainText() == ";pre\n"
    assert reloaded.post_plate_editor.toPlainText() == ";post\n"
    assert reloaded.language_combo.currentData() == "fr"
    assert reloaded.output_directory == tmp_path / "exports"


def test_export_preview_uses_output_folder_and_auto_filename(tmp_path, monkeypatch) -> None:
    qapp()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    window = MainWindow(Translator("zh"))
    window.output_directory = tmp_path / "exports"
    window.source_paths = [
        Path("这是一个非常非常非常非常非常非常非常非常非常非常非常非常长的模型名称用于测试文件名截断行为_alpha.3mf"),
        Path("beta.3mf"),
    ]
    window.queue = [
        QueueEntry(plate("alpha", index=1), copies=1),
        QueueEntry(plate("beta", index=2), copies=1),
    ]

    filename = window.build_export_filename()
    preview = window.build_output_preview_path()
    window._refresh_state()

    assert filename.endswith(".3mf")
    assert "_plus1_Merge_" in filename
    assert len(filename) <= 96
    assert preview == window.output_directory / filename
    assert window.output_folder_label.text() == str(window.output_directory)
    assert window.output_filename_label.text() == filename
    assert window.output_label.text() == str(preview)
