import logging
import re
import sys
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from zup.config_store import ConfigStore
from zup.constants import (
    DEFAULT_CLICKUP_LISTS,
    DEFAULT_INTERVAL_HOURS,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_SCHEDULE_LIST,
    DEFAULT_SCHEDULE_TYPE,
)

LOG = logging.getLogger(__name__)

# Regex for extracting the list ID from a list widget entry like "My List (abc123)"
_LIST_ENTRY_RE = re.compile(r"^(.*)\s+\(([^)]+)\)$")


class TimeSpinner(QSpinBox):
    """
    A QSpinBox that always displays its value with a leading zero.
    """

    def __init__(self, parent=None):
        super(TimeSpinner, self).__init__(parent)

    def textFromValue(self, val):
        return "{:02d}".format(val)


# ---------------------------------------------------------------------------
# List picker dialog
# ---------------------------------------------------------------------------

class _TreeLoaderThread(QThread):
    """
    Background thread that fetches the full ClickUp workspace tree.

    Using QThread (a QObject subclass) instead of QRunnable so that Python
    retains ownership and the signal source is never garbage-collected while
    the thread is running.
    """

    finished = Signal(list)   # emits the workspace tree on success
    error = Signal(str)       # emits an error message on failure

    def __init__(self, user_token: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._user_token = user_token

    def run(self) -> None:
        try:
            from zup.clickup_client import ClickUpClient
            client = ClickUpClient(user_token=self._user_token)
            tree = client.get_workspace_tree()
            self.finished.emit(tree)
        except Exception as exc:
            self.error.emit(str(exc))


class ListPickerDialog(QDialog):
    """
    A dialog that shows the full ClickUp workspace tree and lets the user
    select lists to add to their configuration.

    The user token is passed at construction time (taken from the token field
    in the parent Configuration dialog before it has been saved).
    """

    def __init__(self, user_token: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Add ClickUp Lists"))
        self.setMinimumSize(420, 480)
        self._selected: list[dict] = []   # [{"id": str, "name": str}]

        # Loading label (visible while fetching)
        self._loading_label = QLabel(self.tr("Loading lists from ClickUp..."))
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Tree widget (hidden until loaded)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setVisible(False)

        # Error label (hidden unless something goes wrong)
        self._error_label = QLabel()
        self._error_label.setVisible(False)
        self._error_label.setWordWrap(True)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._accept_action)
        button_box.rejected.connect(self.reject)
        self._ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self._loading_label)
        layout.addWidget(self._tree)
        layout.addWidget(self._error_label)
        layout.addWidget(button_box)
        self.setLayout(layout)

        # Kick off background load. Parenting the thread to self (the dialog)
        # ensures Qt keeps it alive for at least as long as the dialog lives,
        # and Python retains ownership via self._loader.
        self._loader = _TreeLoaderThread(user_token=user_token, parent=self)
        self._loader.finished.connect(self._on_tree_loaded)
        self._loader.error.connect(self._on_tree_error)
        self._loader.start()

    @Slot(list)
    def _on_tree_loaded(self, tree: list) -> None:
        self._loading_label.setVisible(False)
        self._populate_tree(tree)
        self._tree.setVisible(True)
        self._ok_button.setEnabled(True)

    @Slot(str)
    def _on_tree_error(self, message: str) -> None:
        self._loading_label.setVisible(False)
        self._error_label.setText(
            self.tr("Failed to load lists: ") + message
        )
        self._error_label.setVisible(True)

    def _populate_tree(self, tree: list) -> None:
        for space in tree:
            space_item = QTreeWidgetItem(self._tree, [space["name"]])
            space_item.setFlags(space_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

            # Folders within the space
            for folder in space.get("folders", []):
                folder_item = QTreeWidgetItem(space_item, [folder["name"]])
                folder_item.setFlags(
                    folder_item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable
                )
                for lst in folder.get("lists", []):
                    self._add_list_item(folder_item, lst)

            # Folderless lists directly under the space
            for lst in space.get("lists", []):
                self._add_list_item(space_item, lst)

    def _add_list_item(self, parent: QTreeWidgetItem, lst: dict) -> None:
        label = f"{lst['name']} ({lst['id']})"
        item = QTreeWidgetItem(parent, [label])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        item.setData(0, Qt.ItemDataRole.UserRole, lst)

    def _accept_action(self) -> None:
        self._selected = []
        root = self._tree.invisibleRootItem()
        self._collect_checked(root)
        self.accept()

    def _collect_checked(self, parent: QTreeWidgetItem) -> None:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.checkState(0) == Qt.CheckState.Checked:
                data = child.data(0, Qt.ItemDataRole.UserRole)
                if data:
                    self._selected.append(data)
            self._collect_checked(child)

    def selected_lists(self) -> list[dict]:
        """Returns list of {"id": str, "name": str} for all checked items."""
        return self._selected


# ---------------------------------------------------------------------------
# Main configuration dialog
# ---------------------------------------------------------------------------

class Configuration(QDialog):
    """
    Application settings dialog.
    """

    def __init__(self, config_store: ConfigStore, parent=None):
        super(Configuration, self).__init__(parent)
        self.config_store = config_store

        self.schedule_widgets = []
        self.interval_widgets = []

        def managed_widget(widget_list, widget):
            widget_list.append(widget)
            return widget

        self.setWindowTitle(self.tr("Configuration"))
        self.setMinimumWidth(460)

        # --- ClickUp section ---
        self.clickup_token = QLineEdit(
            self.config_store.get("clickup_token", "")
        )
        self.clickup_token.setPlaceholderText(self.tr("ClickUp personal API token"))
        self.clickup_token.setEchoMode(QLineEdit.EchoMode.Password)

        # List of ClickUp lists to pull tasks from
        self._lists_widget = QListWidget()
        self._lists_widget.setMaximumHeight(120)
        for entry in self.config_store.get("clickup_lists_display", []):
            self._lists_widget.addItem(entry)

        add_list_button = QPushButton(self.tr("&Add list..."))
        add_list_button.clicked.connect(self._add_list_action)
        remove_list_button = QPushButton(self.tr("&Remove selected"))
        remove_list_button.clicked.connect(self._remove_list_action)

        lists_buttons_layout = QHBoxLayout()
        lists_buttons_layout.addWidget(add_list_button)
        lists_buttons_layout.addWidget(remove_list_button)
        lists_buttons_layout.addStretch()

        lists_layout = QVBoxLayout()
        lists_layout.addWidget(self._lists_widget)
        lists_layout.addLayout(lists_buttons_layout)

        # --- Schedule section (unchanged) ---
        self.schedule_type_group = QButtonGroup()

        self.schedule_radio_button = QRadioButton(self.tr("Schedule"))
        self.schedule_radio_button.clicked.connect(self._schedule_radio_action)
        self.schedule_type_group.addButton(self.schedule_radio_button)
        schedule_layout = QVBoxLayout()
        schedule_time_layout = QHBoxLayout()
        schedule_time_layout.addSpacing(20)
        schedule_time_layout.addWidget(
            managed_widget(self.schedule_widgets, QLabel(self.tr("New time:")))
        )
        schedule_time_layout.addSpacing(5)
        self.schedule_time_hour = managed_widget(self.schedule_widgets, TimeSpinner())
        self.schedule_time_hour.setMaximumWidth(40)
        self.schedule_time_hour.setRange(0, 23)
        self.schedule_time_hour.setWrapping(True)
        schedule_time_layout.addWidget(self.schedule_time_hour)
        schedule_time_layout.addWidget(
            managed_widget(self.schedule_widgets, QLabel(":"))
        )
        self.schedule_time_minute = managed_widget(self.schedule_widgets, TimeSpinner())
        self.schedule_time_minute.setMaximumWidth(40)
        self.schedule_time_minute.setRange(0, 59)
        self.schedule_time_minute.setWrapping(True)
        schedule_time_layout.addWidget(self.schedule_time_minute)
        schedule_time_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        schedule_time_layout.setSpacing(0)
        add_time_button = managed_widget(
            self.schedule_widgets, QPushButton(self.tr("A&dd"))
        )
        add_time_button.clicked.connect(self._add_time_action)
        schedule_time_layout.addSpacing(5)
        schedule_time_layout.addWidget(add_time_button)
        schedule_layout.addLayout(schedule_time_layout)

        self.schedule_list = managed_widget(self.schedule_widgets, QListWidget())
        self.schedule_list.setMaximumWidth(360)
        self.schedule_list.setSortingEnabled(True)
        for time_value in self.config_store.get("schedule_list", DEFAULT_SCHEDULE_LIST):
            self.schedule_list.addItem(time_value)
        self.schedule_list.itemSelectionChanged.connect(self._schedule_item_action)
        schedule_list_layout = QHBoxLayout()
        schedule_list_layout.addWidget(self.schedule_list)
        schedule_list_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        schedule_layout.addLayout(schedule_list_layout)
        self.remove_time_button = managed_widget(
            self.schedule_widgets, QPushButton(self.tr("Remo&ve"))
        )
        self.remove_time_button.setEnabled(False)
        self.remove_time_button.clicked.connect(self._remove_time_action)
        schedule_remove_layout = QHBoxLayout()
        schedule_remove_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        schedule_remove_layout.addWidget(self.remove_time_button)
        schedule_layout.addLayout(schedule_remove_layout)

        self.interval_radio_button = QRadioButton(self.tr("Interval"))
        self.interval_radio_button.clicked.connect(self._interval_radio_action)
        self.schedule_type_group.addButton(self.interval_radio_button)

        interval_layout = QVBoxLayout()
        interval_time_layout = QHBoxLayout()
        interval_layout.addLayout(interval_time_layout)
        interval_time_layout.addWidget(
            managed_widget(
                self.interval_widgets, QLabel(self.tr("Pop-up interval (HH:MM):"))
            )
        )
        self.interval_time_hour = managed_widget(self.interval_widgets, TimeSpinner())
        self.interval_time_hour.setMaximumWidth(40)
        self.interval_time_hour.setRange(0, 23)
        self.interval_time_hour.setWrapping(True)
        self.interval_time_hour.setValue(
            self.config_store.get("interval_hours", DEFAULT_INTERVAL_HOURS)
        )
        interval_time_layout.addWidget(self.interval_time_hour)
        interval_time_layout.addWidget(
            managed_widget(self.interval_widgets, QLabel(":"))
        )
        self.interval_time_minute = managed_widget(self.interval_widgets, TimeSpinner())
        self.interval_time_minute.setMaximumWidth(40)
        self.interval_time_minute.setRange(0, 59)
        self.interval_time_minute.setWrapping(True)
        self.interval_time_minute.setValue(
            self.config_store.get("interval_minutes", DEFAULT_INTERVAL_MINUTES)
        )
        interval_time_layout.addWidget(self.interval_time_minute)
        interval_time_layout.setSpacing(0)
        interval_time_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save_action)
        button_box.rejected.connect(self._cancel_action)

        layout = QFormLayout()
        layout.addRow(self.tr("ClickUp &Token"), self.clickup_token)
        layout.addRow(self.tr("ClickUp Lists"), lists_layout)
        layout.addRow(self.schedule_radio_button)
        layout.addRow(schedule_layout)
        layout.addRow(self.interval_radio_button)
        layout.addRow(interval_layout)
        layout.addRow(button_box)
        self.setLayout(layout)

        if self.config_store.get("schedule_type", DEFAULT_SCHEDULE_TYPE) == "schedule":
            self.schedule_radio_button.setChecked(True)
            self._schedule_radio_action()
        else:
            self.interval_radio_button.setChecked(True)
            self._interval_radio_action()

    # --- ClickUp list management ---

    def _add_list_action(self) -> None:
        token = self.clickup_token.text().strip()
        if not token:
            QMessageBox.warning(
                self,
                self.tr("No token"),
                self.tr(
                    "Please enter a ClickUp API token before adding lists."
                ),
            )
            return

        # Collect IDs already in the list widget to avoid duplicates
        existing_ids: set[str] = set()
        for i in range(self._lists_widget.count()):
            entry = self._lists_widget.item(i).text()
            m = _LIST_ENTRY_RE.match(entry)
            if m:
                existing_ids.add(m.group(2))

        self._picker = ListPickerDialog(user_token=token, parent=self)
        if self._picker.exec() == QDialog.DialogCode.Accepted:
            for lst in self._picker.selected_lists():
                if lst["id"] not in existing_ids:
                    self._lists_widget.addItem(f"{lst['name']} ({lst['id']})")
                    existing_ids.add(lst["id"])

    def _remove_list_action(self) -> None:
        row = self._lists_widget.currentRow()
        if row >= 0:
            self._lists_widget.takeItem(row)

    # --- Save / Cancel ---

    def _save_action(self) -> None:
        self.config_store.set("clickup_token", self.clickup_token.text().strip())

        display_entries = [
            self._lists_widget.item(i).text()
            for i in range(self._lists_widget.count())
        ]
        # Parse IDs out for runtime use; keep display strings for the UI
        list_ids = []
        for entry in display_entries:
            m = _LIST_ENTRY_RE.match(entry)
            if m:
                list_ids.append(m.group(2))
        self.config_store.set("clickup_lists", list_ids)
        self.config_store.set("clickup_lists_display", display_entries)

        schedule_items = [
            self.schedule_list.item(i).text()
            for i in range(self.schedule_list.count())
        ]
        self.config_store.set("schedule_list", schedule_items)
        self.config_store.set(
            "schedule_type",
            "schedule" if self.schedule_radio_button.isChecked() else "interval",
        )
        self.config_store.set("interval_minutes", self.interval_time_minute.value())
        self.config_store.set("interval_hours", self.interval_time_hour.value())
        self.hide()

    def _cancel_action(self) -> None:
        self.hide()

    # --- Schedule helpers (unchanged logic) ---

    def _schedule_radio_action(self) -> None:
        for widget in self.schedule_widgets:
            if (
                widget == self.remove_time_button
                and self.schedule_list.currentRow() < 0
            ):
                continue
            widget.setEnabled(True)
        for widget in self.interval_widgets:
            widget.setEnabled(False)

    def _interval_radio_action(self) -> None:
        for widget in self.interval_widgets:
            widget.setEnabled(True)
        for widget in self.schedule_widgets:
            widget.setEnabled(False)

    def _add_time_action(self) -> None:
        time_value = "{:02d}:{:02d}".format(
            self.schedule_time_hour.value(), self.schedule_time_minute.value()
        )
        matches = [
            self.schedule_list.item(i)
            for i in range(self.schedule_list.count())
            if self.schedule_list.item(i).text() == time_value
        ]
        if not matches:
            self.schedule_list.addItem(time_value)

    def _remove_time_action(self) -> None:
        self.schedule_list.takeItem(self.schedule_list.currentRow())
        self.remove_time_button.setEnabled(self.schedule_list.count() > 0)

    def _schedule_item_action(self) -> None:
        self.remove_time_button.setEnabled(self.schedule_list.count() > 0)


def main():
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(message)s")
    app = QApplication(sys.argv)
    config_store = ConfigStore()
    configuration_window = Configuration(config_store)
    configuration_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
