"""
A PySide2 (Qt5) application for registering time spent to JIRA issues.
"""
import sys
import os
import logging
import json

from appdirs import user_config_dir
import keyring

from PySide2.QtWidgets import *
from PySide2.QtGui import *
from PySide2.QtCore import *

from jira import JIRA
from requests.compat import urljoin

import pendulum

import zup
from zup.constants import *
from zup.configuration import Configuration
from zup.authcheck import CheckHTTPBasicAuth

LOG = logging.getLogger(__name__)


class JIRAAuthentication(QDialog):
    """
    A GUI component that handles our connection to JIRA and does authentication if
    required.
    """

    authenticated = Signal()

    def __init__(self, url, username, password, parent=None):
        super(JIRAAuthentication, self).__init__(parent)
        self.setWindowTitle(self.tr("JIRA Authentication"))
        self.threadpool = QThreadPool()
        self.jira = None

        self.url = QLineEdit(url)
        self.username = QLineEdit(username)
        self.password = QLineEdit(password)
        self.password.setEchoMode(QLineEdit.Password)
        self.setMinimumWidth(300)

        self.status_label = QLabel("")

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._ok_action)
        self.button_box.rejected.connect(self._cancel_action)

        layout = QFormLayout()
        layout.addRow(self.tr("U&RL"), self.url)
        layout.addRow(self.tr("&Username"), self.username)
        layout.addRow(self.tr("&Password"), self.password)
        layout.addRow(self.status_label)
        layout.addRow(self.button_box)
        self.setLayout(layout)
        self.url.setFocus()
        self._check_authentication(url, username, password)

    def _check_authentication(self, url, username, password):
        LOG.debug(
            "Opening a connection to: %s (username=%s, password=%s)",
            url,
            username,
            "*" * len(password) if password is not None else 0,
        )
        self._inputs_enabled(False)
        basic_checker = CheckHTTPBasicAuth(
            url=urljoin(url, "/rest/api/2/serverInfo"),
            username=username,
            password=password,
        )
        basic_checker.signals.finished.connect(self._authcheck_finished)
        self.threadpool.start(basic_checker)

    def _inputs_enabled(self, state):
        for widget in [self.url, self.username, self.password, self.button_box]:
            widget.setEnabled(state)

    def _ok_action(self):
        self._inputs_enabled(False)
        self._check_authentication(
            self.url.text(), self.username.text(), self.password.text()
        )

    def _cancel_action(self):
        LOG.debug("Cancel.")
        self.close()
        sys.exit(1)

    def _authcheck_finished(self, status):
        LOG.debug("Authentication check finished: %d: %s", status[0], status[1])
        if status[0] == 200:
            Configuration.set("server_url", self.url.text())
            Configuration.set("username", self.username.text())
            keyring.set_password(
                APPLICATION_NAME, self.username.text(), self.password.text()
            )
            self.authenticated.emit()
            self.hide()
        else:
            message = (
                self.tr(status[1])
                if len(status[1]) > 0
                else self.tr("Authentication failed")
            )
            self.status_label.setText('<font color="red">{}</font>'.format(message))
            self._inputs_enabled(True)
            self.url.setFocus()
            self.show()


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
            QIcon("icons/log-work.svg"), self.tr("&Register"), self
        )
        register_button.clicked.connect(self._register_action)

        snooze_button = QToolButton(self)
        snooze_button.setIcon(QIcon("icons/snooze.svg"))
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
        input_layout.addWidget(self.issue_selector)
        input_layout.addWidget(self.duration_selector)
        input_layout.addWidget(register_button)
        input_layout.addWidget(snooze_button)

        self.last_entry_label = QLabel("")

        base_layout = QVBoxLayout()
        base_layout.addLayout(input_layout)
        base_layout.addWidget(self.last_entry_label)
        self.setLayout(base_layout)

        jira_auth = JIRAAuthentication(
            Configuration.get("server_url"),
            Configuration.get("username"),
            keyring.get_password(APPLICATION_NAME, Configuration.get("username")),
            parent,
        )
        jira_auth.authenticated.connect(self._authenticated)

    def closeEvent(self, event):
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

    def _register_action(self):
        self.register_issue_number = self.issue_selector.currentData()
        self.register_time_spent = self.duration_selector.currentData()
        LOG.debug(
            "Register work. Yes: %s: %s",
            self.register_issue_number,
            self.register_time_spent,
        )
        jira_auth = JIRAAuthentication(
            Configuration.get("server_url"),
            Configuration.get("username"),
            keyring.get_password(APPLICATION_NAME, Configuration.get("username")),
            self.parent(),
        )
        jira_auth.authenticated.connect(self._submit_registration)
        next_run = Configuration.get("next_run")
        if len(next_run) == 0 or pendulum.parse(next_run) < pendulum.now():
            LOG.debug("Schedule run in the future")
            if pendulum.now() > pendulum.today().add(hours=14):
                next_run = pendulum.tomorrow().add(hours=11)
            elif pendulum.now() > pendulum.today().add(hours=11):
                next_run = pendulum.today().add(hours=14)
            else:
                next_run = pendulum.today().add(hours=11)
            Configuration.set("next_run", next_run.for_json())
        else:
            LOG.debug("We were probably executed manually. Won't schedule.")
        self.close()

    def _submit_registration(self):
        jira = JIRA(
            Configuration.get("server_url"),
            auth=(
                Configuration.get("username"),
                keyring.get_password(APPLICATION_NAME, Configuration.get("username")),
            ),
        )
        jira.add_worklog(
            jira.issue(self.register_issue_number), self.register_time_spent
        )

    def _authenticated(self):
        LOG.debug("LogWork: We are authenticated.")
        jira = JIRA(
            Configuration.get("server_url"),
            auth=(
                Configuration.get("username"),
                keyring.get_password(APPLICATION_NAME, Configuration.get("username")),
            ),
        )
        latest_issue = None
        latest_worklog = None
        for issue in jira.search_issues(
            "assignee=currentUser() and status in (Open, Ready) and type = Task order by updated",
            maxResults=20,
            fields="worklog,summary,type",
        ):
            issue_label = "{key}: {summary} ({issuetype})".format(
                key=issue.key,
                summary=issue.fields.summary,
                issuetype=issue.fields.issuetype,
            )
            self.issue_selector.addItem(issue_label, issue.id)
            for worklog in issue.fields.worklog.worklogs:
                if latest_worklog is None or pendulum.parse(
                    worklog.created
                ) > pendulum.parse(latest_worklog.created):
                    LOG.debug("Found later worklog")
                    latest_issue = issue
                    latest_worklog = worklog
            last_entry_text = self.tr("Last entry") + ": {date}: {key}: {spent}".format(
                date=pendulum.parse(latest_worklog.created).format(
                    "DD/MM/YYYY HH:MM:SS"
                ),
                key=latest_issue.key,
                spent=latest_worklog.timeSpent,
            )
            self.last_entry_label.setText(last_entry_text)

        self.show()


class SystemTrayIcon(QSystemTrayIcon):
    """
    Create a system-tray icon for Zup and add our very basic menu to it.
    """

    def __init__(self, icon, parent=None):
        QSystemTrayIcon.__init__(self, icon, parent)
        self.parent = parent
        self._logwork_dialog = None
        self.setToolTip(self.tr("Log work to JIRA"))
        self.main_menu = QMenu(parent)
        log_work_item = self.main_menu.addAction(self.tr("Log work now"))
        log_work_item.triggered.connect(self._log_work)
        log_work_item.setIcon(QIcon("icons/log-work.svg"))

        exit_ = self.main_menu.addAction(self.tr("Exit"))
        exit_.triggered.connect(sys.exit)
        exit_.setIcon(QIcon("icons/exit.svg"))

        self.main_menu.addSeparator()
        self.setContextMenu(self.main_menu)
        self.activated.connect(self._activated_action)
        self.wake_timer = QTimer(self.parent)
        self.wake_timer.setTimerType(Qt.VeryCoarseTimer)
        self.wake_timer.timeout.connect(self._timer_tick)
        self.wake_timer.start(60 * 1000)
        self._timer_tick()

    def _activated_action(self, reason):
        if reason == self.Trigger:
            self.main_menu.popup(QCursor.pos())

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
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(message)s")
    app = QApplication(sys.argv)
    root_widget = QWidget()
    tray_icon = SystemTrayIcon(QIcon("icons/zup.svg"), root_widget)
    tray_icon.show()
    tray_icon.showMessage("'zup", app.tr("I'm here in case you need me."))
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
