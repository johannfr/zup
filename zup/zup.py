"""
A PySide6 (Qt6) application for registering time spent to TargetProcess issues.
"""

import logging
import os
import sys

import pendulum
from PySide6.QtCore import QEvent, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from requests.compat import urljoin

from zup.authcheck import CheckHTTPBasicAuth
from zup.configuration import Configuration
from zup.constants import (
    APPLICATION_NAME,
    DEFAULT_INTERVAL_HOURS,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_SCHEDULE_LIST,
    DEFAULT_SCHEDULE_TYPE,
)

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

        self.issue_selector = QComboBox(self)

        self.duration_selector = QComboBox()
        duration_values = [
            [self.tr("4 hours"), "4h"],
            [self.tr("1 hour"), "1h"],
            [self.tr("1 day"), "1d"],
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

        self.last_entry_label = QLabel("")

        base_layout = QVBoxLayout()
        base_layout.addLayout(input_layout)
        base_layout.addWidget(self.last_entry_label)
        self.setLayout(base_layout)
        self.show()

    def closeEvent(self, event):
        LOG.debug("EventHandler: closeEvent")
        event.ignore()
        next_run = Configuration.get("next_run")
        if len(next_run) == 0 or pendulum.parse(next_run) < pendulum.now():
            self._snooze(15)
        else:
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
        self.register_time_spent = self.duration_selector.currentData()
        LOG.debug(
            "Register work. Yes: %s: %s",
            self.register_issue_number,
            self.register_time_spent,
        )
        self._schedule_next_run()
        self.close()

    def _cancel_action(self):
        self._schedule_next_run()
        self.close()

    def _submit_registration(self):
        pass
        # jira = JIRA(
        #     Configuration.get("server_url"),
        #     auth=(
        #         Configuration.get("username"),
        #         keyring.get_password(APPLICATION_NAME, Configuration.get("username")),
        #     ),
        # )
        # jira.add_worklog(
        #     jira.issue(self.register_issue_number), self.register_time_spent
        # )

    def _authenticated(self):
        LOG.debug("LogWork: We are authenticated.")
        # jira = JIRA(
        #     Configuration.get("server_url"),
        #     auth=(
        #         Configuration.get("username"),
        #         keyring.get_password(APPLICATION_NAME, Configuration.get("username")),
        #     ),
        # )
        # latest_issue = None
        # latest_worklog = None
        # for issue in jira.search_issues(
        #     Configuration.get("jira_query", DEFAULT_JIRA_QUERY),
        #     maxResults=20,
        #     fields="worklog,summary,type,created",
        # ):
        #     issue_label = "{key}: {summary} ({issuetype})".format(
        #         key=issue.key,
        #         summary=issue.fields.summary,
        #         issuetype=issue.fields.issuetype,
        #     )
        #     self.issue_selector.addItem(issue_label, issue.id)
        #     for worklog in issue.fields.worklog.worklogs:
        #         if latest_worklog is None or pendulum.parse(
        #             worklog.created
        #         ) > pendulum.parse(latest_worklog.created):
        #             LOG.debug("Found later worklog")
        #             latest_issue = issue
        #             latest_worklog = worklog
        #     try:
        #         last_entry_text = self.tr(
        #             "Last entry"
        #         ) + ": {date}: {key}: {spent}".format(
        #             date=pendulum.parse(latest_worklog.created).format(
        #                 "DD/MM/YYYY HH:MM:SS"
        #             ),
        #             key=latest_issue.key,
        #             spent=latest_worklog.timeSpent,
        #         )
        #     except AttributeError:
        #         last_entry_text = ""
        #     self.last_entry_label.setText(last_entry_text)

        self.show()


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
        LOG.debug("Log work, yes.")

        if self._logwork_dialog is not None:
            self._logwork_dialog.close()
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
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(message)s")
    app = QApplication(sys.argv)
    root_widget = QWidget()
    tray_icon = SystemTrayIcon(QIcon(resolve_icon("zup.png")), root_widget)
    tray_icon.show()
    tray_icon.showMessage("'zup", app.tr("I'm here in case you need me."))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
