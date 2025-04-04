import json
import logging
import os
import sys

from appdirs import user_config_dir
from PySide6.QtCore import Qt
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
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from zup.constants import (
    APPLICATION_AUTHOR,
    APPLICATION_NAME,
    DEFAULT_INTERVAL_HOURS,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_JIRA_QUERY,
    DEFAULT_SCHEDULE_LIST,
    DEFAULT_SCHEDULE_TYPE,
)


class TimeSpinner(QSpinBox):
    """
    A quick-and-dirty way of getting a spinnger with a leading-zero
    """

    def __init__(self, parent=None):
        super(TimeSpinner, self).__init__(parent)

    def textFromValue(self, val):
        return "{:02d}".format(val)


class Configuration(QDialog):
    """
    Class for managing the application configuration.
    """

    def __init__(self, parent=None):
        super(Configuration, self).__init__(parent)

        self.schedule_widgets = []
        self.interval_widgets = []

        def managed_widget(widget_list, widget):
            widget_list.append(widget)
            return widget

        self.setWindowTitle(self.tr("Configuration"))
        self.setMinimumWidth(400)

        self.jql = QLineEdit(Configuration.get("jira_query", DEFAULT_JIRA_QUERY))

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
        schedule_time_layout.setAlignment(Qt.AlignRight)
        schedule_time_layout.setSpacing(0)
        add_time_button = managed_widget(
            self.schedule_widgets, QPushButton(self.tr("&Add"))
        )
        add_time_button.clicked.connect(self._add_time_action)
        schedule_time_layout.addSpacing(5)
        schedule_time_layout.addWidget(add_time_button)
        schedule_layout.addLayout(schedule_time_layout)

        self.schedule_list = managed_widget(self.schedule_widgets, QListWidget())
        self.schedule_list.setMaximumWidth(360)
        self.schedule_list.setSortingEnabled(True)
        for time_value in Configuration.get("schedule_list", DEFAULT_SCHEDULE_LIST):
            self.schedule_list.addItem(time_value)
        self.schedule_list.itemSelectionChanged.connect(self._schedule_item_action)
        schedule_list_layout = QHBoxLayout()
        schedule_list_layout.addWidget(self.schedule_list)
        schedule_list_layout.setAlignment(Qt.AlignRight)
        schedule_layout.addLayout(schedule_list_layout)
        self.remove_time_button = managed_widget(
            self.schedule_widgets, QPushButton(self.tr("&Remove"))
        )
        self.remove_time_button.setEnabled(False)
        self.remove_time_button.clicked.connect(self._remove_time_action)
        schedule_remove_layout = QHBoxLayout()
        schedule_remove_layout.setAlignment(Qt.AlignRight)
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
            Configuration.get("interval_hours", DEFAULT_INTERVAL_HOURS)
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
            Configuration.get("interval_minutes", DEFAULT_INTERVAL_MINUTES)
        )
        interval_time_layout.addWidget(self.interval_time_minute)
        interval_time_layout.setSpacing(0)
        interval_time_layout.setAlignment(Qt.AlignRight)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._save_action)
        button_box.rejected.connect(self._cancel_action)

        layout = QFormLayout()
        layout.addRow(self.tr("JIRA &query"), self.jql)
        layout.addRow(self.schedule_radio_button)
        layout.addRow(schedule_layout)
        layout.addRow(self.interval_radio_button)
        layout.addRow(interval_layout)
        layout.addRow(button_box)
        self.setLayout(layout)
        if Configuration.get("schedule_type", DEFAULT_SCHEDULE_TYPE) == "schedule":
            self.schedule_radio_button.setChecked(True)
            self._schedule_radio_action()
        else:
            self.interval_radio_button.setChecked(True)
            self._interval_radio_action()

    def _save_action(self):
        Configuration.set("jira_query", self.jql.text())
        schedule_items = [
            item.text() for item in self.schedule_list.findItems("*", Qt.MatchWildcard)
        ]
        Configuration.set("schedule_list", schedule_items)
        Configuration.set(
            "schedule_type",
            "schedule" if self.schedule_radio_button.isChecked() else "interval",
        )
        Configuration.set("interval_minutes", self.interval_time_minute.value())
        Configuration.set("interval_hours", self.interval_time_hour.value())
        self.hide()

    def _cancel_action(self):
        self.hide()

    def _schedule_radio_action(self):
        for widget in self.schedule_widgets:
            if (
                widget == self.remove_time_button
                and self.schedule_list.currentRow() < 0
            ):
                continue
            widget.setEnabled(True)
        for widget in self.interval_widgets:
            widget.setEnabled(False)

    def _interval_radio_action(self):
        for widget in self.interval_widgets:
            widget.setEnabled(True)
        for widget in self.schedule_widgets:
            widget.setEnabled(False)

    def _add_time_action(self):
        time_value = "{:02d}:{:02d}".format(
            self.schedule_time_hour.value(), self.schedule_time_minute.value()
        )
        if len(self.schedule_list.findItems(time_value, Qt.MatchExactly)) == 0:
            self.schedule_list.addItem(time_value)

    def _remove_time_action(self):
        self.schedule_list.takeItem(self.schedule_list.currentRow())
        self.remove_time_button.setEnabled(self.schedule_list.count() > 0)

    def _schedule_item_action(self):
        self.remove_time_button.setEnabled(self.schedule_list.count() > 0)

    @staticmethod
    def _read_config():
        """
        Wraps reading the configuration JSON-file
        """
        try:
            return json.load(
                open(
                    os.path.join(
                        user_config_dir(APPLICATION_NAME, APPLICATION_AUTHOR),
                        "config.json",
                    ),
                    "r",
                )
            )
        except (FileNotFoundError, SyntaxError):
            return {}

    @staticmethod
    def get(parameter, default_value=""):
        """
        Reads the specified configuration parameter from file (every time)
        """
        try:
            json_config = Configuration._read_config()
            return json_config[parameter]
        except KeyError:
            return default_value

    @staticmethod
    def set(parameter, value):
        """
        Sets the value of the specified configuration parameter and writes it to disk
        """
        json_config = Configuration._read_config()
        json_config[parameter] = value
        os.makedirs(
            os.path.join(
                user_config_dir(APPLICATION_NAME, APPLICATION_AUTHOR),
            ),
            exist_ok=True,
        )
        json.dump(
            json_config,
            open(
                os.path.join(
                    user_config_dir(APPLICATION_NAME, APPLICATION_AUTHOR), "config.json"
                ),
                "w",
            ),
        )


def main():
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(message)s")
    app = QApplication(sys.argv)
    configuration_window = Configuration()
    configuration_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
