"""PyQt6 desktop application."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QLocale, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from change_plate_next.adapters.connect.bambu_connect_launcher import BambuConnectLauncher
from change_plate_next.application.workflow import ChangePlateWorkflow
from change_plate_next.domain.channel_mapping import aggregate_filament_usage, auto_assign_channels, validate_channel_assignments
from change_plate_next.domain.errors import ChangePlateError
from change_plate_next.domain.models import PlateChangeRecipe, QueueEntry
from change_plate_next.interfaces.desktop.i18n import Translator, language_from_locale
from change_plate_next.interfaces.desktop.settings_store import DesktopSettings, load_settings, save_settings
from change_plate_next.interfaces.desktop.theme import app_icon_path, apply_theme
from change_plate_next.resources.defaults import load_default_change_gcode, load_default_sound_gcode

APP_TITLE = "ChangePlatAutoNext"
DEFAULT_CHANGE_GCODE = load_default_change_gcode()
DEFAULT_SOUND_GCODE = load_default_sound_gcode()


class StepperSpinBox(QWidget):
    """Large explicit +/- stepper used instead of platform spin arrows."""

    def __init__(self) -> None:
        super().__init__()
        self._minimum = 0
        self._maximum = 99
        self._value = 0
        self.editor = QLineEdit("0")
        self.decrease_button = QToolButton()
        self.increase_button = QToolButton()
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("StepperSpinBox")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.editor.setObjectName("StepperEditor")
        self.editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.editor.editingFinished.connect(self._commit_text_value)

        self.increase_button.setObjectName("StepperButton")
        self.increase_button.setText("+")
        self.increase_button.clicked.connect(lambda: self.setValue(self._value + 1))

        self.decrease_button.setObjectName("StepperButton")
        self.decrease_button.setText("−")
        self.decrease_button.clicked.connect(lambda: self.setValue(self._value - 1))

        buttons = QVBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(0)
        buttons.addWidget(self.increase_button)
        buttons.addWidget(self.decrease_button)

        layout.addWidget(self.editor, 1)
        layout.addLayout(buttons)

    def _commit_text_value(self) -> None:
        try:
            value = int(self.editor.text())
        except ValueError:
            value = self._value
        self.setValue(value)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = minimum
        self._maximum = maximum
        self.setValue(self._value)

    def setValue(self, value: int) -> None:
        self._value = max(self._minimum, min(self._maximum, int(value)))
        self.editor.setText(str(self._value))

    def value(self) -> int:
        return self._value


class SourceQueueTable(QTableWidget):
    """Table that emits row move requests instead of relying on item-only internal moves."""

    row_move_requested = pyqtSignal(int, int)

    def __init__(self, rows: int, columns: int) -> None:
        super().__init__(rows, columns)
        self._drag_source_row = -1

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override name
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        self._drag_source_row = self.rowAt(position.y())
        super().mousePressEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override name
        source_row = self._drag_source_row if self._drag_source_row >= 0 else self.currentRow()
        if source_row < 0:
            event.ignore()
            return

        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_row = self.indexAt(position).row()
        if target_row < 0:
            target_row = self.rowCount()
        elif self.dropIndicatorPosition() == QAbstractItemView.DropIndicatorPosition.BelowItem:
            target_row += 1
        self.row_move_requested.emit(source_row, target_row)
        self._drag_source_row = -1
        event.acceptProposedAction()


@dataclass(frozen=True, slots=True)
class NavItem:
    """Navigation item metadata used by the left rail."""

    key: str
    page_name: str


NAV_ITEMS = (
    NavItem("nav.compose", "compose"),
    NavItem("nav.channels", "channels"),
    NavItem("nav.gcode_profile", "gcode"),
    NavItem("nav.export", "export"),
    NavItem("nav.settings", "settings"),
)


class MainWindow(QMainWindow):
    """Fluent-style desktop workflow for composing sliced 3MF files into one package."""

    def __init__(self, translator: Translator | None = None) -> None:
        super().__init__()
        self.settings = load_settings()
        default_language = translator.language if translator is not None else self.settings.language or language_from_locale(QLocale.system().name())
        self.tr = translator or Translator(default_language)
        self.workflow = ChangePlateWorkflow.create_default()
        self.connect_launcher = BambuConnectLauncher()
        self.source_paths: list[Path] = []
        self.queue: list[QueueEntry] = []
        self.output_directory: Path | None = Path(self.settings.output_directory).expanduser() if self.settings.output_directory else None
        self.last_output: Path | None = None
        self.current_page_index = 0

        self.status_label = QLabel()
        self.sources_value = QLabel("0")
        self.channels_value = QLabel("0")
        self.export_value = QLabel("--")
        self.sources_table = SourceQueueTable(0, 7)
        self.channels_table = QTableWidget(0, 5)
        self.change_editor = QPlainTextEdit(self.settings.change_gcode or DEFAULT_CHANGE_GCODE)
        self.sound_editor = QPlainTextEdit(self.settings.sound_gcode or DEFAULT_SOUND_GCODE)
        self.pre_plate_editor = QPlainTextEdit(self.settings.pre_plate_gcode)
        self.post_plate_editor = QPlainTextEdit(self.settings.post_plate_gcode)
        self.output_label = QLabel()
        self.output_folder_label = QLabel()
        self.output_filename_label = QLabel()
        self.log_label = QLabel()
        self.language_combo = QComboBox()
        self.settings_language_label = QLabel()
        self.m73_check = QCheckBox()
        self.start_fix_check = QCheckBox()
        self.append_check = QCheckBox()
        self.cooldown_check = QCheckBox()
        self.wait_check = QCheckBox()
        self.sound_tip_check = QCheckBox()
        self.hotbed_temp_spin = StepperSpinBox()
        self.wait_seconds_spin = StepperSpinBox()
        self.sound_tip_count_spin = StepperSpinBox()
        self.advanced_toggle = QToolButton()
        self.advanced_container = QWidget()
        self.export_button = QPushButton()
        self.connect_button = QPushButton()
        self.clear_queue_button = QPushButton()
        self.nav_buttons: list[QPushButton] = []
        self.page_stack = QStackedWidget()
        self.page_title_label = QLabel()
        self.page_caption_label = QLabel()
        self.sources_hint = QLabel()

        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon(app_icon_path()))
        self.resize(1280, 840)
        self.setMinimumSize(1040, 700)
        self.setCentralWidget(self._build_shell())
        self._load_settings_into_controls()
        self._bind_settings_persistence()
        self._apply_translations()
        self.set_page(0)
        self._refresh_state()

    def _load_settings_into_controls(self) -> None:
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.tr.language)))
        self.start_fix_check.setChecked(self.settings.apply_start_position_fix)
        self.m73_check.setChecked(self.settings.encode_plate_number_in_m73)
        self.append_check.setChecked(self.settings.append_if_marker_missing)
        self.cooldown_check.setChecked(self.settings.wait_hotbed_cool)
        self.hotbed_temp_spin.setValue(self.settings.hotbed_temp)
        self.wait_check.setChecked(self.settings.wait_before_next_plate)
        self.wait_seconds_spin.setValue(self.settings.wait_seconds)
        self.sound_tip_check.setChecked(self.settings.sound_tip_when_waiting)
        self.sound_tip_count_spin.setValue(self.settings.sound_tip_count)

    def _bind_settings_persistence(self) -> None:
        self.language_combo.currentIndexChanged.connect(self._persist_settings)
        self.start_fix_check.toggled.connect(self._persist_settings)
        self.m73_check.toggled.connect(self._persist_settings)
        self.append_check.toggled.connect(self._persist_settings)
        self.cooldown_check.toggled.connect(self._persist_settings)
        self.wait_check.toggled.connect(self._persist_settings)
        self.sound_tip_check.toggled.connect(self._persist_settings)
        self.change_editor.textChanged.connect(self._persist_settings)
        self.sound_editor.textChanged.connect(self._persist_settings)
        self.pre_plate_editor.textChanged.connect(self._persist_settings)
        self.post_plate_editor.textChanged.connect(self._persist_settings)
        for spin in (self.hotbed_temp_spin, self.wait_seconds_spin, self.sound_tip_count_spin):
            spin.editor.editingFinished.connect(self._persist_settings)
            spin.increase_button.clicked.connect(self._persist_settings)
            spin.decrease_button.clicked.connect(self._persist_settings)

    def _persist_settings(self) -> None:
        self.settings = DesktopSettings(
            language=str(self.language_combo.currentData() or self.tr.language),
            output_directory=str(self.output_directory) if self.output_directory else "",
            change_gcode=self.change_editor.toPlainText() or DEFAULT_CHANGE_GCODE,
            sound_gcode=self.sound_editor.toPlainText() or DEFAULT_SOUND_GCODE,
            pre_plate_gcode=self.pre_plate_editor.toPlainText(),
            post_plate_gcode=self.post_plate_editor.toPlainText(),
            apply_start_position_fix=self.start_fix_check.isChecked(),
            encode_plate_number_in_m73=self.m73_check.isChecked(),
            append_if_marker_missing=self.append_check.isChecked(),
            wait_hotbed_cool=self.cooldown_check.isChecked(),
            hotbed_temp=self.hotbed_temp_spin.value(),
            wait_before_next_plate=self.wait_check.isChecked(),
            wait_seconds=self.wait_seconds_spin.value(),
            sound_tip_when_waiting=self.sound_tip_check.isChecked(),
            sound_tip_count=self.sound_tip_count_spin.value(),
        )
        save_settings(self.settings)

    def _build_shell(self) -> QWidget:
        root = QWidget()
        root.setObjectName("AppRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._command_bar())
        layout.addWidget(self._body(), 1)
        return root

    def _command_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("CommandBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(12)

        title_block = QVBoxLayout()
        title_block.setSpacing(1)
        title = QLabel(APP_TITLE)
        title.setObjectName("AppTitle")
        self.caption_label = QLabel()
        self.caption_label.setObjectName("WindowCaption")
        title_block.addWidget(title)
        title_block.addWidget(self.caption_label)

        self.status_label.setProperty("status", "info")

        import_button = QPushButton()
        import_button.setObjectName("SubtleButton")
        import_button.clicked.connect(self.import_3mf)
        self.import_button = import_button
        self.clear_queue_button.setObjectName("SubtleButton")
        self.clear_queue_button.clicked.connect(self.clear_queue)

        self.export_button.setObjectName("PrimaryButton")
        self.export_button.clicked.connect(self.export_3mf)
        self.connect_button.setObjectName("SubtleButton")
        self.connect_button.clicked.connect(self.open_in_bambu_connect)

        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Français", "fr")
        self.language_combo.addItem("中文", "zh")
        self.language_combo.setMinimumWidth(120)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.tr.language)))
        self.language_combo.currentIndexChanged.connect(self.change_language)

        layout.addLayout(title_block)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        layout.addWidget(import_button)
        layout.addWidget(self.clear_queue_button)
        layout.addWidget(self.export_button)
        layout.addWidget(self.connect_button)
        return bar

    def _body(self) -> QWidget:
        body = QWidget()
        body.setObjectName("Body")
        layout = QHBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)
        layout.addWidget(self._navigation(), 0)
        layout.addWidget(self._content(), 1)
        return body

    def _navigation(self) -> QFrame:
        nav = QFrame()
        nav.setObjectName("NavigationView")
        nav.setFixedWidth(224)
        layout = QVBoxLayout(nav)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(6)

        self.nav_workspace_label = QLabel()
        self.nav_workspace_label.setObjectName("NavSectionLabel")
        layout.addWidget(self.nav_workspace_label)

        for index, item in enumerate(NAV_ITEMS):
            button = QPushButton()
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setProperty("active", "true" if index == 0 else "false")
            button.clicked.connect(lambda _checked=False, page=index: self.set_page(page))
            button.setProperty("page_name", item.page_name)
            self.nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)
        footer = QLabel("GPL-3.0-only")
        footer.setObjectName("NavFooter")
        layout.addWidget(footer)
        return nav

    def _content(self) -> QFrame:
        surface = QFrame()
        surface.setObjectName("ContentSurface")
        layout = QVBoxLayout(surface)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(18)
        layout.addWidget(self._page_header())
        layout.addWidget(self.page_stack, 1)
        self.page_stack.addWidget(self._compose_page())
        self.page_stack.addWidget(self._channels_page())
        self.page_stack.addWidget(self._gcode_page())
        self.page_stack.addWidget(self._export_page())
        self.page_stack.addWidget(self._settings_page())
        return surface

    def _page_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("PageHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        self.page_title_label.setObjectName("PageHeaderTitle")
        self.page_caption_label.setObjectName("PageHeaderCaption")
        self.page_caption_label.setWordWrap(True)
        title_block.addWidget(self.page_title_label)
        title_block.addWidget(self.page_caption_label)
        layout.addLayout(title_block, 1)
        return header

    def _compose_page(self) -> QWidget:
        page = self._scroll_page()
        layout = self._page_layout(page)
        layout.addWidget(self._hero())
        layout.addLayout(self._metrics())
        layout.addWidget(self._sources_card(), 1)
        return page

    def _channels_page(self) -> QWidget:
        page = self._scroll_page()
        layout = self._page_layout(page)
        layout.addWidget(self._helper_card("channels.help.title", "channels.help.description"))
        layout.addWidget(self._channels_card(), 1)
        return page

    def _gcode_page(self) -> QWidget:
        page = self._scroll_page()
        layout = self._page_layout(page)
        layout.addWidget(self._gcode_options_card())
        layout.addWidget(self._gcode_editors_card(), 1)
        return page

    def _export_page(self) -> QWidget:
        page = self._scroll_page()
        layout = self._page_layout(page)
        layout.addWidget(self._export_card(), 1)
        return page

    def _settings_page(self) -> QWidget:
        page = self._scroll_page()
        layout = self._page_layout(page)
        layout.addWidget(self._settings_summary_card())
        layout.addStretch(1)
        return page

    def _scroll_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName("PageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("PageContent")
        scroll.setWidget(content)
        return scroll

    @staticmethod
    def _page_layout(scroll: QScrollArea) -> QVBoxLayout:
        content = scroll.widget()
        if content is None:
            raise RuntimeError("Page scroll area has no content widget.")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        return layout

    def _hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("HeroCard")
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        self.hero_pill = QLabel()
        self.hero_pill.setProperty("status", "success")
        self.hero_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.hero_title = QLabel()
        self.hero_title.setObjectName("PageTitle")
        self.hero_title.setWordWrap(True)
        self.hero_description = QLabel()
        self.hero_description.setObjectName("HeroText")
        self.hero_description.setWordWrap(True)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.hero_start_button = QPushButton()
        self.hero_start_button.setObjectName("PrimaryButton")
        self.hero_start_button.clicked.connect(self.import_3mf)
        self.docs_button = QPushButton()
        self.docs_button.setObjectName("SubtleButton")
        self.docs_button.clicked.connect(lambda: self.set_page(4))
        actions.addWidget(self.hero_start_button)
        actions.addWidget(self.docs_button)
        actions.addStretch(1)

        layout.addWidget(self.hero_pill)
        layout.addWidget(self.hero_title)
        layout.addWidget(self.hero_description)
        layout.addLayout(actions)
        return hero

    def _metrics(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.addWidget(self._metric_card(self.sources_value, "metric.sources.label"), 0, 0)
        grid.addWidget(self._metric_card(self.channels_value, "metric.channels.label"), 0, 1)
        grid.addWidget(self._metric_card(self.export_value, "metric.export.label"), 0, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        return grid

    def _metric_card(self, value_label: QLabel, label_key: str) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)
        value_label.setObjectName("MetricValue")
        label_widget = QLabel()
        label_widget.setObjectName("MetricLabel")
        label_widget.setProperty("i18n_key", label_key)
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        return card

    def _card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("PanelCard")
        return card

    def _sources_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self.sources_title = QLabel()
        self.sources_title.setObjectName("SectionTitle")
        self.sources_hint.setObjectName("BodyText")
        self.sources_hint.setWordWrap(True)
        self.sources_table.setHorizontalHeaderLabels(["Order", "Preview", "Model", "Copies", "Time", "Weight", "3MF"])
        self._configure_table(self.sources_table, min_height=360, allow_row_drag=True)
        self.sources_table.setWordWrap(True)
        self._set_table_resize_modes(self.sources_table, stretch_columns={2, 6})
        self._configure_sources_columns()
        self.sources_table.row_move_requested.connect(self.move_queue_row)
        layout.addWidget(self.sources_title)
        layout.addWidget(self.sources_hint)
        layout.addWidget(self.sources_table, 1)
        return card

    def _gcode_options_card(self) -> QFrame:
        card = self._card()
        layout = QGridLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(14)
        self.settings_title = QLabel()
        self.settings_title.setObjectName("SectionTitle")
        self.start_fix_check.setChecked(True)
        self.hotbed_temp_spin.setRange(40, 120)
        self.hotbed_temp_spin.setValue(40)
        self.wait_seconds_spin.setRange(0, 3600)
        self.wait_seconds_spin.setValue(120)
        self.sound_tip_count_spin.setRange(1, 100)
        self.sound_tip_count_spin.setValue(10)
        for spin in (self.hotbed_temp_spin, self.wait_seconds_spin, self.sound_tip_count_spin):
            spin.setMinimumHeight(48)
            spin.setMinimumWidth(156)

        self.advanced_toggle.setObjectName("SectionToggle")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.clicked.connect(self._toggle_advanced_settings)
        self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self.advanced_container.setObjectName("AdvancedCard")
        advanced_layout = QVBoxLayout(self.advanced_container)
        advanced_layout.setContentsMargins(14, 10, 14, 10)
        advanced_layout.setSpacing(12)
        advanced_layout.addWidget(self.start_fix_check)
        advanced_layout.addWidget(self.m73_check)
        advanced_layout.addWidget(self.append_check)
        self.advanced_container.setVisible(False)

        layout.addWidget(self.settings_title, 0, 0, 1, 2)
        layout.addWidget(self.cooldown_check, 1, 0, 1, 2)
        layout.addWidget(self._labeled_widget("label.hotbed_temp", self.hotbed_temp_spin), 2, 0, 1, 2)
        layout.addWidget(self.wait_check, 3, 0, 1, 2)
        layout.addWidget(self._labeled_widget("label.wait_seconds", self.wait_seconds_spin), 4, 0, 1, 2)
        layout.addWidget(self.sound_tip_check, 5, 0, 1, 2)
        layout.addWidget(self._labeled_widget("label.sound_tip_count", self.sound_tip_count_spin), 6, 0, 1, 2)
        layout.addWidget(self.advanced_toggle, 7, 0, 1, 2)
        layout.addWidget(self.advanced_container, 8, 0, 1, 2)
        return card

    def _gcode_editors_card(self) -> QFrame:
        card = self._card()
        layout = QGridLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(10)
        self.pre_plate_title = QLabel()
        self.pre_plate_title.setObjectName("SectionTitle")
        self.change_gcode_title = QLabel()
        self.change_gcode_title.setObjectName("SectionTitle")
        self.post_plate_title = QLabel()
        self.post_plate_title.setObjectName("SectionTitle")
        self.sound_gcode_title = QLabel()
        self.sound_gcode_title.setObjectName("SectionTitle")
        for editor in (self.pre_plate_editor, self.change_editor, self.post_plate_editor, self.sound_editor):
            editor.setObjectName("GcodeEditor")
            editor.setMinimumHeight(150)

        layout.addWidget(self.pre_plate_title, 0, 0)
        layout.addWidget(self.pre_plate_editor, 1, 0)
        layout.addWidget(self.change_gcode_title, 0, 1)
        layout.addWidget(self.change_editor, 1, 1)
        layout.addWidget(self.post_plate_title, 2, 0)
        layout.addWidget(self.post_plate_editor, 3, 0)
        layout.addWidget(self.sound_gcode_title, 2, 1)
        layout.addWidget(self.sound_editor, 3, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        return card

    def _channels_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self.channels_title = QLabel()
        self.channels_title.setObjectName("SectionTitle")
        self.channels_table.setHorizontalHeaderLabels(["Channel", "Color", "Material", "Used g", "Source"])
        self._configure_table(self.channels_table, min_height=360)
        self._set_table_resize_modes(self.channels_table, stretch_columns={2, 4})
        layout.addWidget(self.channels_title)
        layout.addWidget(self.channels_table, 1)
        return card

    def _export_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self.export_title = QLabel()
        self.export_title.setObjectName("SectionTitle")
        choose_output = QPushButton()
        choose_output.setObjectName("SubtleButton")
        choose_output.clicked.connect(self.choose_output)
        self.choose_output_button = choose_output
        self.output_folder_title = QLabel()
        self.output_folder_title.setObjectName("FormLabel")
        self.output_filename_title = QLabel()
        self.output_filename_title.setObjectName("FormLabel")
        self.output_preview_title = QLabel()
        self.output_preview_title.setObjectName("FormLabel")
        self.output_folder_label.setObjectName("OutputPathLabel")
        self.output_folder_label.setWordWrap(True)
        self.output_filename_label.setObjectName("OutputPathLabel")
        self.output_filename_label.setWordWrap(True)
        self.output_label.setObjectName("OutputPathLabel")
        self.output_label.setWordWrap(True)
        self.log_label.setObjectName("LogLabel")
        self.log_label.setWordWrap(True)
        layout.addWidget(self.export_title)
        layout.addWidget(choose_output, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.output_folder_title)
        layout.addWidget(self.output_folder_label)
        layout.addWidget(self.output_filename_title)
        layout.addWidget(self.output_filename_label)
        layout.addWidget(self.output_preview_title)
        layout.addWidget(self.output_label)
        layout.addWidget(self.log_label)
        layout.addStretch(1)
        return card

    def _helper_card(self, title_key: str, description_key: str) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        title = QLabel()
        title.setObjectName("SectionTitle")
        title.setProperty("i18n_key", title_key)
        body = QLabel()
        body.setObjectName("BodyText")
        body.setProperty("i18n_key", description_key)
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        return card

    def _settings_summary_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.settings_summary_title = QLabel()
        self.settings_summary_title.setObjectName("SectionTitle")
        self.settings_summary_body = QLabel()
        self.settings_summary_body.setObjectName("BodyText")
        self.settings_summary_body.setWordWrap(True)
        self.settings_language_label.setObjectName("FormLabel")
        language_row = QWidget()
        language_layout = QHBoxLayout(language_row)
        language_layout.setContentsMargins(0, 0, 0, 0)
        language_layout.setSpacing(16)
        language_layout.addWidget(self.settings_language_label)
        language_layout.addStretch(1)
        language_layout.addWidget(self.language_combo)
        layout.addWidget(self.settings_summary_title)
        layout.addWidget(self.settings_summary_body)
        layout.addWidget(language_row)
        return card

    def _labeled_widget(self, label_key: str, widget: QWidget) -> QWidget:
        row = QWidget()
        row.setObjectName("FormRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        label = QLabel()
        label.setObjectName("FormLabel")
        label.setProperty("i18n_key", label_key)
        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(widget)
        return row

    def _toggle_advanced_settings(self, checked: bool) -> None:
        self.advanced_container.setVisible(checked)
        self.advanced_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    @staticmethod
    def _configure_table(table: QTableWidget, *, min_height: int, allow_row_drag: bool = False) -> None:
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setMinimumHeight(min_height)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setStretchLastSection(False)
        if allow_row_drag:
            table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            table.setDragDropOverwriteMode(False)
            table.setDefaultDropAction(Qt.DropAction.MoveAction)
        else:
            table.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)

    @staticmethod
    def _set_table_resize_modes(table: QTableWidget, *, stretch_columns: set[int]) -> None:
        header = table.horizontalHeader()
        for column in range(table.columnCount()):
            mode = QHeaderView.ResizeMode.Stretch if column in stretch_columns else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(column, mode)

    def _configure_sources_columns(self) -> None:
        header = self.sources_table.horizontalHeader()
        fixed_widths = {
            0: 68,
            1: 104,
            3: 124,
            4: 128,
            5: 96,
        }
        for column, width in fixed_widths.items():
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.sources_table.setColumnWidth(column, width)

    def set_page(self, index: int) -> None:
        if index < 0 or index >= len(NAV_ITEMS):
            return
        self.current_page_index = index
        self.page_stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            active = button_index == index
            button.setChecked(active)
            button.setProperty("active", "true" if active else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        self.page_title_label.setText(self.tr.text(f"page.{NAV_ITEMS[index].page_name}.title"))
        self.page_caption_label.setText(self.tr.text(f"page.{NAV_ITEMS[index].page_name}.caption"))

    def _apply_translations(self) -> None:
        self.caption_label.setText(self.tr.text("app.caption"))
        self.status_label.setText(self.tr.text("status.ready"))
        self.import_button.setText(self.tr.text("button.import_3mf"))
        self.clear_queue_button.setText(self.tr.text("button.clear_queue"))
        self.export_button.setText(self.tr.text("button.export"))
        self.connect_button.setText(self.tr.text("button.open_bambu"))
        self.nav_workspace_label.setText(self.tr.text("nav.workspace"))
        for button, item in zip(self.nav_buttons, NAV_ITEMS, strict=True):
            button.setText(self.tr.text(item.key))
        self.hero_pill.setText(self.tr.text("hero.pill"))
        self.hero_title.setText(self.tr.text("hero.title"))
        self.hero_description.setText(self.tr.text("hero.description"))
        self.hero_start_button.setText(self.tr.text("button.start_3mf"))
        self.docs_button.setText(self.tr.text("button.open_docs"))
        self.sources_title.setText(self.tr.text("section.sources"))
        self.sources_hint.setText(self.tr.text("table.sources.hint"))
        self.settings_title.setText(self.tr.text("section.gcode_settings"))
        self.channels_title.setText(self.tr.text("section.channels"))
        self.export_title.setText(self.tr.text("section.export"))
        self.choose_output_button.setText(self.tr.text("button.output_path"))
        self.output_folder_title.setText(self.tr.text("label.output_folder"))
        self.output_filename_title.setText(self.tr.text("label.output_filename"))
        self.output_preview_title.setText(self.tr.text("label.output_preview"))
        self.start_fix_check.setText(self.tr.text("option.start_fix"))
        self.m73_check.setText(self.tr.text("option.m73"))
        self.append_check.setText(self.tr.text("option.append_missing_marker"))
        self.cooldown_check.setText(self.tr.text("option.cooldown"))
        self.wait_check.setText(self.tr.text("option.wait_between_plates"))
        self.sound_tip_check.setText(self.tr.text("option.sound_tip"))
        self.advanced_toggle.setText(self.tr.text("section.advanced_settings"))
        self.pre_plate_title.setText(self.tr.text("section.pre_plate_gcode"))
        self.change_gcode_title.setText(self.tr.text("section.change_gcode"))
        self.post_plate_title.setText(self.tr.text("section.post_plate_gcode"))
        self.sound_gcode_title.setText(self.tr.text("section.sound_gcode"))
        self.settings_summary_title.setText(self.tr.text("settings.summary.title"))
        self.settings_summary_body.setText(self.tr.text("settings.summary.body"))
        self.settings_language_label.setText(self.tr.text("label.language"))
        self._toggle_advanced_settings(self.advanced_toggle.isChecked())
        self.sources_table.setHorizontalHeaderLabels(
            [
                self.tr.text("table.sources.order"),
                self.tr.text("table.sources.preview"),
                self.tr.text("table.sources.model"),
                self.tr.text("table.sources.copies"),
                self.tr.text("table.sources.time"),
                self.tr.text("table.sources.weight"),
                self.tr.text("table.sources.file"),
            ]
        )
        self._configure_sources_columns()
        self.channels_table.setHorizontalHeaderLabels(
            [
                self.tr.text("table.channels.channel"),
                self.tr.text("table.channels.color"),
                self.tr.text("table.channels.material"),
                self.tr.text("table.channels.used"),
                self.tr.text("table.channels.source"),
            ]
        )
        for label in self.findChildren(QLabel):
            key = label.property("i18n_key")
            if key:
                label.setText(self.tr.text(str(key)))
        self.set_page(self.current_page_index)
        self._refresh_state()

    def change_language(self) -> None:
        language = self.language_combo.currentData()
        if language:
            self.tr = Translator(str(language))
            self._apply_translations()
            self._persist_settings()

    def import_3mf(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, self.tr.text("dialog.import_title"), "", "3MF (*.3mf)")
        if not paths:
            return
        try:
            new_paths = [Path(path) for path in paths]
            queue = self.workflow.build_queue_from_packages(new_paths, copies=1, auto_map=False)
        except Exception as exc:
            self._show_error(exc)
            return
        self.source_paths.extend(path for path in new_paths if path not in self.source_paths)
        self.queue.extend(queue)
        auto_assign_channels(self.queue)
        self.last_output = None
        self._log(
            self.tr.text("log.imported").format(
                imported_count=len(new_paths),
                total_files=len(self.source_paths),
                total_items=len(self.queue),
            )
        )
        self._refresh_state()
        self.set_page(0)

    def clear_queue(self) -> None:
        self.source_paths.clear()
        self.queue.clear()
        self.last_output = None
        self._log(self.tr.text("log.queue_cleared"))
        self._refresh_state()

    def update_row_copies(self, row: int, value: int) -> None:
        if 0 <= row < len(self.queue):
            self.queue[row].copies = value
            self._refresh_source_row(row)
        self._refresh_derived_state()

    def move_queue_row(self, source_row: int, target_row: int) -> None:
        if source_row < 0 or source_row >= len(self.queue):
            return
        if target_row < 0:
            target_row = 0
        if target_row > len(self.queue):
            target_row = len(self.queue)
        item = self.queue.pop(source_row)
        if target_row > source_row:
            target_row -= 1
        self.queue.insert(target_row, item)
        self._refresh_state()

    def choose_output(self) -> None:
        start_dir = str(self.output_directory or Path.cwd())
        path = QFileDialog.getExistingDirectory(self, self.tr.text("dialog.output_title"), start_dir)
        if path:
            self.output_directory = Path(path)
            self._persist_settings()
            self._refresh_state()

    @staticmethod
    def _sanitize_filename_part(text: str) -> str:
        sanitized = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in text)
        sanitized = " ".join(sanitized.split()).strip(" ._")
        return sanitized or "Merged"

    def build_export_filename(self) -> str:
        date_code = datetime.now().strftime("%Y%m%d")
        source_names = [path.stem for path in self.source_paths if path.stem]
        if source_names:
            base_name = self._sanitize_filename_part(source_names[0])
            if len(source_names) > 1:
                base_name = f"{base_name}_plus{len(source_names) - 1}"
        else:
            base_name = "Merged"
        suffix = f"_Merge_{date_code}"
        max_base_length = 72
        if len(base_name) > max_base_length:
            base_name = base_name[:max_base_length].rstrip(" ._")
        return f"{base_name}{suffix}.3mf"

    def build_output_preview_path(self) -> Path | None:
        if self.output_directory is None:
            return None
        return self.output_directory / self.build_export_filename()

    def export_3mf(self) -> None:
        if not self.queue:
            QMessageBox.information(self, APP_TITLE, self.tr.text("message.import_first"))
            return
        output_path = self.build_output_preview_path()
        if output_path is None:
            self.choose_output()
            output_path = self.build_output_preview_path()
            if output_path is None:
                return
        try:
            recipe = PlateChangeRecipe(
                change_gcode=self.change_editor.toPlainText() or DEFAULT_CHANGE_GCODE,
                sound_gcode=self.sound_editor.toPlainText(),
                pre_plate_gcode=self.pre_plate_editor.toPlainText(),
                post_plate_gcode=self.post_plate_editor.toPlainText(),
                apply_start_position_fix=self.start_fix_check.isChecked(),
                encode_plate_number_in_m73=self.m73_check.isChecked(),
                wait_hotbed_cool=self.cooldown_check.isChecked(),
                hotbed_temp=self.hotbed_temp_spin.value(),
                wait_before_next_plate=self.wait_check.isChecked(),
                wait_seconds=self.wait_seconds_spin.value(),
                sound_tip_when_waiting=self.sound_tip_check.isChecked(),
                sound_tip_count=self.sound_tip_count_spin.value(),
            )
            if self.append_check.isChecked():
                from change_plate_next.domain.policies import InsertionStrategy

                recipe = PlateChangeRecipe(
                    change_gcode=recipe.change_gcode,
                    sound_gcode=recipe.sound_gcode,
                    pre_plate_gcode=recipe.pre_plate_gcode,
                    post_plate_gcode=recipe.post_plate_gcode,
                    apply_start_position_fix=recipe.apply_start_position_fix,
                    encode_plate_number_in_m73=recipe.encode_plate_number_in_m73,
                    wait_hotbed_cool=recipe.wait_hotbed_cool,
                    hotbed_temp=recipe.hotbed_temp,
                    wait_before_next_plate=recipe.wait_before_next_plate,
                    wait_seconds=recipe.wait_seconds,
                    sound_tip_when_waiting=recipe.sound_tip_when_waiting,
                    sound_tip_count=recipe.sound_tip_count,
                    insertion_strategy=InsertionStrategy.APPEND_WITH_WARNING,
                )
            result = self.workflow.export_queue(self.queue, recipe, output_path)
        except Exception as exc:
            self._show_error(exc)
            return
        self.last_output = result.output_path
        self.export_value.setText(self.tr.text("export.done"))
        self.connect_button.setEnabled(True)
        self._log(self.tr.text("log.exported").format(path=result.output_path))
        if result.warnings:
            self._log("\n".join(result.warnings))
        QMessageBox.information(self, APP_TITLE, self.tr.text("message.export_done").format(path=result.output_path))

    def open_in_bambu_connect(self) -> None:
        if self.last_output is None or not self.last_output.exists():
            return
        ok = self.connect_launcher.open_import(self.last_output, self.last_output.name)
        if not ok:
            QMessageBox.warning(self, APP_TITLE, self.tr.text("message.connect_failed"))

    def _refresh_state(self) -> None:
        self.sources_value.setText(str(len(self.queue)))
        self._refresh_sources_table()
        self._refresh_derived_state()

    def _refresh_derived_state(self) -> None:
        try:
            aggregates = aggregate_filament_usage(self.queue) if self.queue else ()
        except Exception:
            aggregates = ()
        self.channels_value.setText(str(len(aggregates)))
        if not self.queue:
            self.export_value.setText("--")
        self.export_button.setEnabled(bool(self.queue))
        self.connect_button.setEnabled(bool(self.last_output and self.last_output.exists()))
        preview_path = self.build_output_preview_path()
        self.output_folder_label.setText(
            str(self.output_directory) if self.output_directory else self.tr.text("output.folder_not_selected")
        )
        self.output_filename_label.setText(
            self.build_export_filename() if self.queue else self.tr.text("output.filename_empty")
        )
        self.output_label.setText(
            str(preview_path) if preview_path and self.queue else self.tr.text("output.folder_not_selected")
        )
        self._refresh_channels_table(aggregates)
        conflicts = validate_channel_assignments(self.queue) if self.queue else []
        if conflicts:
            self.status_label.setText(self.tr.text("status.blocked"))
            self.status_label.setProperty("status", "danger")
        else:
            self.status_label.setText(self.tr.text("status.ready"))
            self.status_label.setProperty("status", "info")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _refresh_sources_table(self) -> None:
        self.sources_table.blockSignals(True)
        self.sources_table.setRowCount(len(self.queue))
        for row, item in enumerate(self.queue):
            self.sources_table.setRowHeight(row, 92)
            self._set_source_row_values(row, item)
            self.sources_table.setCellWidget(row, 1, self._preview_widget(item))
            copies_spin = StepperSpinBox()
            copies_spin.setRange(0, 99)
            copies_spin.setObjectName("CopiesSpin")
            copies_spin.setMinimumWidth(96)
            copies_spin.setMaximumWidth(96)
            copies_spin.setMinimumHeight(34)
            copies_spin.setValue(max(0, int(item.copies)))
            copies_spin.editor.editingFinished.connect(
                lambda table_row=row, widget=copies_spin: self.update_row_copies(table_row, widget.value())
            )
            copies_spin.increase_button.clicked.connect(
                lambda _checked=False, table_row=row, widget=copies_spin: self.update_row_copies(table_row, widget.value())
            )
            copies_spin.decrease_button.clicked.connect(
                lambda _checked=False, table_row=row, widget=copies_spin: self.update_row_copies(table_row, widget.value())
            )
            self.sources_table.setCellWidget(row, 3, copies_spin)
        self.sources_table.blockSignals(False)
        self.sources_table.resizeColumnsToContents()
        self._configure_sources_columns()

    def _refresh_source_row(self, row: int) -> None:
        if not 0 <= row < len(self.queue):
            return
        self._set_source_row_values(row, self.queue[row])
        self.sources_table.resizeColumnsToContents()

    def _set_source_row_values(self, row: int, item: QueueEntry) -> None:
        values = [
            f"#{row + 1}",
            "",
            f"{item.plate.display_name}\nplate_{item.plate.source_index}",
            "",
            self._format_seconds(item.plate.prediction_seconds * item.copies),
            f"{item.plate.weight_g * item.copies:.2f} g",
            item.plate.source_package.name,
        ]
        self._set_table_row(self.sources_table, row, values)

    def _preview_widget(self, item: QueueEntry) -> QLabel:
        label = QLabel()
        label.setObjectName("PlatePreview")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(88, 72)
        preview_path = item.plate.assets.preview or item.plate.assets.small_preview or item.plate.assets.top_preview
        pixmap = QPixmap(str(preview_path)) if preview_path and preview_path.exists() else QPixmap()
        if pixmap.isNull():
            label.setText(self.tr.text("table.sources.no_preview"))
            return label
        label.setPixmap(pixmap.scaled(QSize(82, 66), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        return label

    def _refresh_channels_table(self, aggregates: Iterable[object]) -> None:
        aggregates_list = list(aggregates)
        self.channels_table.setRowCount(len(aggregates_list))
        for row, item in enumerate(aggregates_list):
            values = [
                str(int(item.channel)),
                item.source.signature.color,
                item.source.signature.material or "--",
                f"{item.used_g:.2f}",
                f"local {int(item.source.local_id)}",
            ]
            self._set_table_row(self.channels_table, row, values)
        self.channels_table.resizeColumnsToContents()

    @staticmethod
    def _set_table_row(table: QTableWidget, row: int, values: list[str]) -> None:
        for col, value in enumerate(values):
            table_item = QTableWidgetItem(value)
            table_item.setFlags(table_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, col, table_item)

    def _show_error(self, exc: Exception) -> None:
        if isinstance(exc, ChangePlateError):
            message = exc.detail.message
            if exc.detail.suggestion:
                message += f"\n\n{exc.detail.suggestion}"
        else:
            message = str(exc)
        self._log(message)
        QMessageBox.critical(self, APP_TITLE, message)

    def _log(self, text: str) -> None:
        self.log_label.setText(text)

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        total = int(seconds)
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m {secs}s"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    app.setWindowIcon(QIcon(app_icon_path()))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
