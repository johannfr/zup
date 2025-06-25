"""
Handles reading and writing configuration to a file.
"""

import json
import logging
import os
from typing import Any

from appdirs import user_config_dir
from PySide6.QtCore import QMutex, QMutexLocker

from zup.constants import APPLICATION_AUTHOR, APPLICATION_NAME

LOG = logging.getLogger(__name__)


class ConfigStore:
    """
    A class for managing the application's configuration data.
    """

    _instance = None
    _lock = QMutex()

    def __new__(cls):
        if cls._instance is None:
            with QMutexLocker(cls._lock):
                if cls._instance is None:
                    cls._instance = super(ConfigStore, cls).__new__(cls)
                    cls._instance._config = cls._instance._read_config()
        return cls._instance

    def _get_config_path(self) -> str:
        """Returns the path to the configuration file."""
        config_dir = user_config_dir(APPLICATION_NAME, APPLICATION_AUTHOR)
        return os.path.join(config_dir, "config.json")

    def _read_config(self) -> dict:
        """
        Reads the configuration JSON-file.
        """
        try:
            with open(self._get_config_path(), "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def get(self, parameter: str, default_value: Any = "") -> Any:
        """
        Reads the specified configuration parameter.
        """
        return self._config.get(parameter, default_value)

    def set(self, parameter: str, value: Any) -> None:
        """
        Sets the value of the specified configuration parameter and writes it to disk.
        """
        self._config[parameter] = value
        self._write_config()

    def _write_config(self) -> None:
        """
        Writes the configuration to disk.
        """
        config_path = self._get_config_path()
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(self._config, f, indent=4)
