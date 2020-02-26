import zup
from zup.constants import *

import os
import json
from appdirs import user_config_dir


class Configuration:
    """
    A collection of (static) helper-functions for reading the application configuration.
    """

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
    def get(parameter):
        """
        Reads the specified configuration parameter from file (every time)
        """
        try:
            json_config = Configuration._read_config()
            return json_config[parameter]
        except KeyError:
            return ""

    @staticmethod
    def set(parameter, value):
        """
        Sets the value of the specified configuration parameter and writes it to disk
        """
        json_config = Configuration._read_config()
        json_config[parameter] = value
        os.makedirs(
            os.path.join(user_config_dir(APPLICATION_NAME, APPLICATION_AUTHOR),),
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
