from PySide2.QtCore import *
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import MissingSchema
from requests.exceptions import ConnectionError as RConnectionError


class CheckAuthSignals(QObject):
    finished = Signal(tuple)


class CheckHTTPBasicAuth(QRunnable):
    def __init__(self, url, username, password):
        super(CheckHTTPBasicAuth, self).__init__()
        self.signals = CheckAuthSignals()
        self.url = url
        self.username = username
        self.password = password

    @Slot()
    def run(self):
        try:
            probe_get = requests.get(
                self.url, auth=HTTPBasicAuth(self.username, self.password),
            )
            self.signals.finished.emit([probe_get.status_code, probe_get.reason])
        except MissingSchema:
            self.signals.finished.emit([-1, "Missing schema"])
        except RConnectionError:
            self.signals.finished.emit([-2, "Connection error"])
        except UnboundLocalError:
            self.signals.finished.emit([-3, "Authentication failed"])
