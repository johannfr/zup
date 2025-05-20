"""
A PySide6 (Qt6) application for registering time spent to TargetProcess issues.
"""

import json
import logging
import os
import sys

import pendulum
import requests
from PySide6.QtCore import QEvent, QRunnable, Qt, QThreadPool, QTimer, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from requests.compat import urljoin

from zup.configuration import Configuration
from zup.constants import (
    DEFAULT_INTERVAL_HOURS,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_SCHEDULE_LIST,
    DEFAULT_SCHEDULE_TYPE,
    DEFAULT_TP_TAKE,
    DEFAULT_TP_URL,
)
from zup.logging import RedactingFormatter

redact_patterns = [
    (r"access_token=\w+", "access_token=****"),
]

log_handler = logging.StreamHandler()
log_formatter = RedactingFormatter(
    fmt="%(levelname)-8s %(filename)s:%(lineno)d %(funcName)s %(message)s",
    redact_patterns=redact_patterns,
)
log_handler.setFormatter(log_formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(log_handler)

LOG = logging.getLogger(__name__)


def resolve_icon(filename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", filename)


class LogWorkDialog(QDialog):
    """
    This is the main log-work dialog of this application.
    """

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(self.tr("Log Work"))
        self.installEventFilter(self)
        self.alive = True
        self.internal_close_flag = False
        self.submit_thread_pool = QThreadPool()

        self.issue_selector = QComboBox(self)
        self.issue_selector.setEditable(True)
        relevant_issues = []
        for issue in self._retrieve_relevant_issues():
            issue_display_string = f"TP{issue['Id']}: {issue['Name']}"
            relevant_issues.append(issue_display_string)
            self.issue_selector.addItem(issue_display_string, int(issue["Id"]))

        completer = QCompleter(relevant_issues)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.issue_selector.setCompleter(completer)

        self.duration_selector = QComboBox()
        duration_values = [
            [self.tr("4 hours"), 4],
            [self.tr("1 hour"), 1],
            [self.tr("1 day"), 8],
        ]
        for duration in duration_values:
            self.duration_selector.addItem(*duration)
        register_button = QPushButton(
            QIcon(resolve_icon("log-work.png")), self.tr("&Register"), self
        )
        register_button.clicked.connect(self._register_action)
        cancel_button = QPushButton(
            QIcon(resolve_icon("cancel.png")), self.tr("&Cancel")
        )
        cancel_button.clicked.connect(self._cancel_action)

        snooze_button = QToolButton(self)
        snooze_button.setIcon(QIcon(resolve_icon("snooze.png")))
        snooze_button.setPopupMode(QToolButton.InstantPopup)
        snooze_menu = QMenu(self)
        snooze_menu.addAction(self.tr("15 minutes"), lambda: self._snooze(15))
        snooze_menu.addAction(self.tr("30 minutes"), lambda: self._snooze(30))
        snooze_menu.addAction(self.tr("1 hour"), lambda: self._snooze(60))
        snooze_menu.addAction(self.tr("4 hours"), lambda: self._snooze(4 * 60))
        snooze_menu.addAction(self.tr("Next day"), lambda: self._snooze(-1))
        snooze_menu.addAction(self.tr("Next Monday"), lambda: self._snooze(-2))
        snooze_button.setMenu(snooze_menu)

        input_layout = QHBoxLayout()
        input_layout.addWidget(snooze_button)
        input_layout.addWidget(self.issue_selector)
        input_layout.addWidget(self.duration_selector)
        input_layout.addWidget(register_button)
        input_layout.addWidget(cancel_button)

        self.toggle_history_button = QToolButton()
        self.toggle_history_button.setText("Registration history")
        self.toggle_history_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toggle_history_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_history_button.setCheckable(True)
        self.toggle_history_button.setChecked(False)
        self.toggle_history_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_history_button.toggled.connect(self.toggle_log_content)

        self.log_widget = QWidget()
        self.log_layout = QVBoxLayout(self.log_widget)
        for item in reversed(Configuration.get("registration_history", [])):
            item_datetime = pendulum.parse(item["datetime"]).format(
                "YYYY-MM-DD HH:MM:ss"
            )
            self.log_layout.addWidget(
                QLabel(
                    f"{item_datetime}: {item['issue_title']}: {item['time_spent']} hours"
                )
            )
        self.log_layout.addStretch(1)
        self.log_widget.setVisible(False)

        last_registration_issue_number = Configuration.get(
            "last_registration_issue_number", -1
        )
        if last_registration_issue_number != -1:
            last_index = self.issue_selector.findData(last_registration_issue_number)
            if last_index >= 0:
                self.issue_selector.setCurrentIndex(last_index)

        base_layout = QVBoxLayout()
        base_layout.addLayout(input_layout)
        base_layout.addWidget(self.toggle_history_button)
        base_layout.addWidget(self.log_widget)
        base_layout.addStretch(1)
        self.setLayout(base_layout)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.show()

        # Center the dialog on the screen
        screen = QApplication.primaryScreen()
        dialog_geometry = self.frameGeometry()
        center_point = screen.geometry().center()
        dialog_geometry.moveCenter(center_point)
        self.move(dialog_geometry.topLeft())

    @Slot(bool)
    def toggle_log_content(self, checked):
        if checked:
            self.toggle_history_button.setArrowType(Qt.ArrowType.DownArrow)
            self.toggle_history_button.setText("")
            self.log_widget.setVisible(True)
        else:
            self.toggle_history_button.setArrowType(Qt.ArrowType.RightArrow)
            self.toggle_history_button.setText("Registration history")
            self.log_widget.setVisible(False)
            QTimer.singleShot(1, self.adjustSize)

    def internal_close(self):
        self.internal_close_flag = True
        self.close()
        self.internal_close_flag = False

    def closeEvent(self, event):
        LOG.debug("EventHandler: closeEvent")
        event.ignore()
        if self.internal_close_flag:
            LOG.debug("EventHandler: closeEvent: Internal close. Not doing anything.")
            self.hide()
            return
        next_run = Configuration.get("next_run")
        if len(next_run) == 0 or pendulum.parse(next_run) < pendulum.now():
            LOG.debug("Snoozing due to closeEvent")
            self._snooze(15)
        else:
            LOG.debug("Just closing.")
            self.hide()

    def eventFilter(self, widget, event):
        if event.type() == QEvent.KeyPress and event.key() in (
            Qt.Key_Enter,
            Qt.Key_Return,
            Qt.Key_Escape,
        ):
            LOG.debug("Ignoring keystroke")
            return True
        else:
            return super(LogWorkDialog, self).eventFilter(widget, event)

    def _retrieve_relevant_issues(self):
        get_params = {
            "access_token": Configuration.get("tp_access_token", ""),
            "orderByDesc": "Assignable.Id",
            "format": "json",
            "take": Configuration.get("tp_take", DEFAULT_TP_TAKE),
            "where": f"(Team.Name eq '{Configuration.get('tp_team_name', '')}')"
            "and(Assignable.EntityType.Name eq 'UserStory')"
            "and(EntityState.Name ne 'Done')",
        }
        api_request = requests.get(
            urljoin(
                Configuration.get("tp_url", DEFAULT_TP_URL), "/api/v1/TeamAssignments"
            ),
            params=get_params,
        )
        if api_request.status_code == 200:
            return [x["Assignable"] for x in json.loads(api_request.text)["Items"]]
        else:
            return []

    def _snooze(self, duration):
        if duration > 0:
            LOG.debug("Snooze: Normal duration: %d", duration)
            next_run = pendulum.now().add(minutes=duration)
        else:
            LOG.debug("Snooze: Special duration: %d", duration)
            if duration == -1:
                next_run = pendulum.tomorrow().add(hours=6)
            elif duration == -2:
                next_run = pendulum.now().next(pendulum.MONDAY).add(hours=6)

        Configuration.set("next_run", next_run.for_json())
        self.hide()

    def _schedule_next_run(self):
        next_run = Configuration.get("next_run")
        if len(next_run) == 0 or pendulum.parse(next_run) < pendulum.now():
            LOG.debug("Schedule run in the future")
            if Configuration.get("schedule_type", DEFAULT_SCHEDULE_TYPE) == "schedule":
                scheduled_run = None
                for time_value in Configuration.get(
                    "schedule_list", DEFAULT_SCHEDULE_LIST
                ):
                    hours, minutes = time_value.split(":")
                    pendulum_time = pendulum.today().add(
                        hours=int(hours), minutes=int(minutes)
                    )
                    if pendulum_time > pendulum.now():
                        scheduled_run = pendulum_time
                        break
                if scheduled_run is None:
                    hours, minutes = Configuration.get(
                        "schedule_list", DEFAULT_SCHEDULE_LIST
                    )[0].split(":")
                    scheduled_run = pendulum.tomorrow().add(
                        hours=int(hours), minutes=int(minutes)
                    )
            else:
                interval_hours = Configuration.get(
                    "interval_hours", DEFAULT_INTERVAL_HOURS
                )
                interval_minutes = Configuration.get(
                    "interval_minutes", DEFAULT_INTERVAL_MINUTES
                )
                scheduled_run = pendulum.now().add(
                    hours=interval_hours, minutes=interval_minutes
                )
            LOG.debug("Next run scheduled at: %s", scheduled_run)
            Configuration.set("next_run", scheduled_run.for_json())
        else:
            LOG.debug("We were probably executed manually. Won't schedule.")

    def _register_action(self):
        self.register_issue_number = self.issue_selector.currentData()
        self.register_issue_title = self.issue_selector.currentText()
        self.register_time_spent = self.duration_selector.currentData()
        self.submit_thread_pool.start(QRunnable.create(self.submit_registration))
        registration_history = Configuration.get("registration_history", [])
        registration_history.append(
            {
                "datetime": str(pendulum.now()),
                "issue_number": self.register_issue_number,
                "issue_title": self.register_issue_title,
                "time_spent": self.register_time_spent,
            }
        )
        registration_history = registration_history[-5:]
        Configuration.set("registration_history", registration_history)

        Configuration.set("last_registration_issue_number", self.register_issue_number)
        self._schedule_next_run()
        self.internal_close()

    def _cancel_action(self):
        self._schedule_next_run()
        self.internal_close()

    def submit_registration(self):
        LOG.debug(
            "Submit a registration: %s: %d hours",
            self.register_issue_number,
            self.register_time_spent,
        )
        json_payload = {
            "User": {"Id": Configuration.get("tp_userid", "")},
            "Spent": self.register_time_spent,
            "Description": ".",
            "Assignable": {"Id": self.register_issue_number},
        }

        params = {"access_token": Configuration.get("tp_access_token", "")}

        requests.post(
            urljoin(Configuration.get("tp_url", ""), "/api/v1/times"),
            params=params,
            json=json_payload,
        )

        LOG.debug("Done Submitting.")


class SystemTrayIcon(QSystemTrayIcon):
    """
    Create a system-tray icon for Zup and add our very basic menu to it.
    """

    def __init__(self, icon, parent=None):
        QSystemTrayIcon.__init__(self, icon, parent)
        self.parent = parent
        self._logwork_dialog = None
        self._settings_dialog = None
        self.setToolTip(self.tr("Log work to TargetProcess"))
        self.main_menu = QMenu(parent)
        log_work_item = self.main_menu.addAction(self.tr("Log work now"))
        log_work_item.triggered.connect(self._log_work)
        log_work_item.setIcon(QIcon(resolve_icon("log-work.png")))

        settings_item = self.main_menu.addAction(self.tr("Settings"))
        settings_item.setIcon(QIcon(resolve_icon("settings.png")))
        settings_item.triggered.connect(self._settings_action)

        exit_ = self.main_menu.addAction(self.tr("Exit"))
        exit_.triggered.connect(sys.exit)
        exit_.setIcon(QIcon(resolve_icon("exit.png")))

        self.main_menu.addSeparator()
        self.setContextMenu(self.main_menu)
        self.activated.connect(self._activated_action)

        # Set up a wake-timer that checks every minute if it is time to show a
        # LogWorkDialog.
        self.wake_timer = QTimer(self.parent)
        self.wake_timer.setTimerType(Qt.VeryCoarseTimer)
        self.wake_timer.timeout.connect(self._timer_tick)
        self.wake_timer.start(60 * 1000)
        self._timer_tick()

    def _activated_action(self, reason):
        LOG.debug(reason)
        # if reason == self.ActivationReason.Trigger:
        #     self.main_menu.popup(QCursor.pos())

    def _settings_action(self):
        LOG.debug("Open settings window")
        if self._settings_dialog is not None:
            self._settings_dialog.close()
            self._settings_dialog.destroy()
        self._settings_dialog = Configuration(self.parent)
        self._settings_dialog.show()

    def _log_work(self):
        LOG.debug("Open LogWorkDialog.")

        if self._logwork_dialog is not None:
            self._logwork_dialog.internal_close()
            self._logwork_dialog.destroy()
        self._logwork_dialog = LogWorkDialog(self.parent)

    def _timer_tick(self):
        try:
            if self._logwork_dialog.isVisible():
                LOG.debug("Window is already open.")
                return
        except AttributeError:
            pass

        next_run = Configuration.get("next_run")
        if len(next_run) == 0:
            LOG.debug("We have never executed. We should do that right now..")
            self._log_work()
        else:
            next_run = pendulum.parse(next_run)
            LOG.debug("Next run at/after: %s", next_run)
            if next_run <= pendulum.now():
                LOG.debug("It's time to pop up the registration window")
                self._log_work()


def main():
    Configuration.set("next_run", "")

    app = QApplication(sys.argv)
    root_widget = QWidget()
    tray_icon = SystemTrayIcon(QIcon(resolve_icon("zup.png")), root_widget)
    tray_icon.show()
    tray_icon.showMessage("'zup", app.tr("I'm here in case you need me."))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
