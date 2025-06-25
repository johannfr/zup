"""
A PySide6 (Qt6) application for registering time spent to TargetProcess issues.
"""

import logging
import os
import sys
from typing import Optional

import pendulum
from PySide6.QtCore import QEvent, QRunnable, Qt, QThreadPool, QTimer
from PySide6.QtGui import QCloseEvent, QIcon
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

from zup.config_store import ConfigStore
from zup.configuration import Configuration
from zup.constants import (
    DEFAULT_INTERVAL_HOURS,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_SCHEDULE_LIST,
    DEFAULT_SCHEDULE_TYPE,
)
from zup.targetprocess_client import TargetProcessClient

LOG = logging.getLogger(__name__)


def resolve_icon(filename: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", filename)


class LogWorkDialog(QDialog):
    """
    This is the main log-work dialog of this application.
    """

    def __init__(self, config_store: ConfigStore, parent: Optional[QWidget] = None) -> None:
        QDialog.__init__(self, parent)
        self.config_store = config_store
        self.setWindowTitle(self.tr("Log Work"))
        self.installEventFilter(self)
        self.alive = True
        self.submit_thread_pool = QThreadPool()
        self.tp_client = TargetProcessClient(self.config_store)

        self.issue_selector = QComboBox(self)
        self.issue_selector.setEditable(True)
        relevant_issues = []
        for issue in self.tp_client.get_relevant_issues():
            issue_display_string = f"TP{issue['Id']}: {issue['Name']}"
            relevant_issues.append(issue_display_string)
            self.issue_selector.addItem(issue_display_string, int(issue["Id"]))

        completer = QCompleter(relevant_issues)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.issue_selector.setCompleter(completer)

        popup = completer.popup()
        popup.setWindowFlags(Qt.WindowType.ToolTip)

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
        snooze_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
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

        last_registration_issue_number = self.config_store.get(
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

    def closeEvent(self, event: QCloseEvent) -> None:
        LOG.debug("EventHandler: closeEvent")
        event.ignore()
        if self.internal_close_flag:
            LOG.debug("EventHandler: closeEvent: Internal close. Not doing anything.")
            self.hide()
            return
        next_run = self.config_store.get("next_run")
        if len(next_run) == 0 or pendulum.parse(next_run) < pendulum.now():
            LOG.debug("Snoozing due to closeEvent")
            self._snooze(15)
        else:
            LOG.debug("Just closing.")
            self.hide()

    def eventFilter(self, widget: QWidget, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Enter,
            Qt.Key.Key_Return,
            Qt.Key.Key_Escape,
        ):
            LOG.debug("Ignoring keystroke")
            return True
        else:
            return super(LogWorkDialog, self).eventFilter(widget, event)

    def _snooze(self, duration: int) -> None:
        if duration > 0:
            LOG.debug("Snooze: Normal duration: %d", duration)
            next_run = pendulum.now().add(minutes=duration)
        else:
            LOG.debug("Snooze: Special duration: %d", duration)
            if duration == -1:
                next_run = pendulum.tomorrow().add(hours=6)
            elif duration == -2:
                next_run = pendulum.now().next(pendulum.MONDAY).add(hours=6)

        self.config_store.set("next_run", next_run.for_json())
        self.hide()

    def _schedule_next_run(self) -> None:
        next_run = self.config_store.get("next_run")
        if len(next_run) == 0 or pendulum.parse(next_run) < pendulum.now():
            LOG.debug("Schedule run in the future")
            if self.config_store.get("schedule_type", DEFAULT_SCHEDULE_TYPE) == "schedule":
                scheduled_run = None
                for time_value in self.config_store.get(
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
                    hours, minutes = self.config_store.get(
                        "schedule_list", DEFAULT_SCHEDULE_LIST
                    )[0].split(":")
                    scheduled_run = pendulum.tomorrow().add(
                        hours=int(hours), minutes=int(minutes)
                    )
            else:
                interval_hours = self.config_store.get(
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

    def _register_action(self) -> None:
        issue_number = self.issue_selector.currentData()
        time_spent = self.duration_selector.currentData()

        self.submit_thread_pool.start(
            QRunnable.create(
                self.tp_client.submit_time_registration, issue_number, time_spent
            )
        )

        self.config_store.set("last_registration_issue_number", issue_number)
        self.config_store.set("last_registration_time_spent", time_spent)
        self.config_store.set("last_registration_datetime", str(pendulum.now()))
        self._schedule_next_run()
        self.close()

    def _cancel_action(self) -> None:
        self._schedule_next_run()
        self.close()


class SystemTrayIcon(QSystemTrayIcon):
    """
    Create a system-tray icon for Zup and add our very basic menu to it.
    """

    def __init__(self, icon: QIcon, parent: Optional[QWidget] = None) -> None:
        QSystemTrayIcon.__init__(self, icon, parent)
        self.parent = parent
        self.config_store = ConfigStore()
        self._logwork_dialog: Optional[LogWorkDialog] = None
        self._settings_dialog: Optional[Configuration] = None
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
        self.wake_timer.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self.wake_timer.timeout.connect(self._timer_tick)
        self.wake_timer.start(60 * 1000)
        self._timer_tick()

    def _activated_action(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        LOG.debug(reason)
        # if reason == self.ActivationReason.Trigger:
        #     self.main_menu.popup(QCursor.pos())

    def _settings_action(self) -> None:
        LOG.debug("Open settings window")
        if self._settings_dialog is not None:
            self._settings_dialog.close()
            self._settings_dialog.destroy()
        self._settings_dialog = Configuration(self.parent)
        self._settings_dialog.show()

    def _log_work(self) -> None:
        LOG.debug("Open LogWorkDialog.")

        if self._logwork_dialog is not None:
            self._logwork_dialog.internal_close()
            self._logwork_dialog.destroy()
        self._logwork_dialog = LogWorkDialog(self.config_store, self.parent)

    def _timer_tick(self) -> None:
        try:
            if self._logwork_dialog.isVisible():
                LOG.debug("Window is already open.")
                return
        except AttributeError:
            pass

        next_run = self.config_store.get("next_run")
        if len(next_run) == 0:
            LOG.debug("We have never executed. We should do that right now..")
            self._log_work()
        else:
            next_run = pendulum.parse(next_run)
            LOG.debug("Next run at/after: %s", next_run)
            if next_run <= pendulum.now():
                LOG.debug("It's time to pop up the registration window")
                self._log_work()


def main() -> None:
    config_store = ConfigStore()
    config_store.set("next_run", "")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)-8s %(funcName)s:%(filename)s:%(lineno)d %(message)s",
    )
    app = QApplication(sys.argv)
    root_widget = QWidget()
    tray_icon = SystemTrayIcon(QIcon(resolve_icon("zup.png")), root_widget)
    tray_icon.show()
    tray_icon.showMessage("'zup", app.tr("I'm here in case you need me."))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

