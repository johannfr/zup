"""
A simple client for the TargetProcess API.
"""

import json
import logging
from typing import Any, Dict, List

import requests
from requests.compat import urljoin

from zup.configuration import Configuration
from zup.constants import (
    DEFAULT_TP_TAKE,
    DEFAULT_TP_TEAM_NAME,
    DEFAULT_TP_URL,
    DEFAULT_TP_WHERE,
)

LOG = logging.getLogger(__name__)


class TargetProcessClient:
    """
    A client for interacting with the TargetProcess API.
    """

    def __init__(self, configuration: Configuration):
        self.configuration = configuration

    def get_relevant_issues(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of relevant issues from TargetProcess.
        """

        where_items = {
            "team_name": self.configuration.get("tp_team_name", DEFAULT_TP_TEAM_NAME),
            "user_id": self.configuration.get("tp_userid", ""),
        }
        get_params = {
            "access_token": self.configuration.get("tp_access_token", ""),
            "orderByDesc": "Assignable.Id",
            "format": "json",
            "take": self.configuration.get("tp_take", DEFAULT_TP_TAKE),
            "where": self.configuration.get("tp_where", DEFAULT_TP_WHERE).format(
                **where_items
            ),
        }
        api_request = requests.get(
            urljoin(
                self.configuration.get("tp_url", DEFAULT_TP_URL),
                "/api/v1/TeamAssignments",
            ),
            params=get_params,
        )
        if api_request.status_code == 200:
            return [x["Assignable"] for x in json.loads(api_request.text)["Items"]]
        else:
            return []

    def submit_time_registration(self, issue_id: int, time_spent: float) -> None:
        """
        Submits a time registration to TargetProcess.
        """
        LOG.debug(
            "Submit a registration: %s: %d hours",
            issue_id,
            time_spent,
        )
        json_payload = {
            "User": {"Id": self.configuration.get("tp_userid", "")},
            "Spent": time_spent,
            "Description": ".",
            "Assignable": {"Id": issue_id},
        }

        params = {"access_token": self.configuration.get("tp_access_token", "")}

        requests.post(
            urljoin(self.configuration.get("tp_url", ""), "/api/v1/times"),
            params=params,
            json=json_payload,
        )

        LOG.debug("Done Submitting.")
