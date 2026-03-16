"""
ClickUp client for fetching tasks and registering time.

The ClickUpClient class is the primary interface used by the application.
It mirrors the interface of the old TargetProcessClient:
  - get_relevant_issues(list_ids) -> list of {"id": str, "name": str}
  - submit_time_registration(issue_id, decimal_hours)

Time is expressed in decimal hours throughout the application (e.g. 0.5 = 30 min).
The client converts to milliseconds when calling the ClickUp API.

The user token is passed at construction time. The caller (zup.py) is responsible
for reading it from ConfigStore. This module has no knowledge of ConfigStore.
"""

import logging

from clickup_python_sdk.api import ClickupClient
from clickup_python_sdk.clickupobjects.task import Task

LOG = logging.getLogger(__name__)

TERMINAL_STATUSES = {"done", "closed", "complete", "completed"}

_DECIMAL_HOURS_TO_MS = 3600 * 1000


_NOT_FETCHED = object()  # sentinel distinguishing "not yet fetched" from None


class ClickUpClient:
    """
    Application-level ClickUp client.

    Wraps the clickup_python_sdk and provides the interface expected by
    the rest of the application.
    """

    def __init__(self, user_token: str) -> None:
        self._user_token = user_token
        self._client: ClickupClient | None = None
        # Cached team ID (str) or None if workspace has no teams.
        self._team_id: str | None | object = _NOT_FETCHED
        # Cached numeric custom_item_id for the "Release" task type, or None.
        self._release_type_id: int | None | object = _NOT_FETCHED

    def _get_client(self) -> ClickupClient:
        """Lazily initialise the underlying SDK client (makes a network call)."""
        if self._client is None:
            self._client = ClickupClient.init(user_token=self._user_token)
            user = self._client.TOKEN_USER
            LOG.debug(
                "Authorised as: %s (email=%s, id=%s)",
                user["username"],
                user["email"],
                user["id"],
            )
        return self._client

    def _get_team_id(self) -> str | None:
        """Return the first workspace/team ID, cached after the first call."""
        if self._team_id is not _NOT_FETCHED:
            return self._team_id  # type: ignore[return-value]
        teams = self._get_client().get_teams()
        if teams:
            LOG.debug("Available workspaces:")
            for team in teams:
                LOG.debug("  [%s] %s", team["id"], team["name"])
            self._team_id = teams[0]["id"]
            LOG.debug("Using workspace: %s (%s)", teams[0]["name"], teams[0]["id"])
        else:
            LOG.debug("No workspaces found for this token.")
            self._team_id = None
        return self._team_id  # type: ignore[return-value]

    def _get_release_type_id(self) -> int | None:
        """
        Return the numeric custom_item_id for the "Release" task type, or None.

        The result is fetched once per session and cached on the instance.
        Requires the SDK singleton to be initialised before calling.
        """
        if self._release_type_id is not _NOT_FETCHED:
            return self._release_type_id  # type: ignore[return-value]

        try:
            team_id = self._get_team_id()
            if not team_id:
                self._release_type_id = None
                return None
            response = self._get_client().make_request(
                method="GET", route=f"team/{team_id}/custom_item"
            )
            response_data: dict = response or {}  # type: ignore[assignment]
            custom_items = response_data.get("custom_items", [])
            if custom_items:
                LOG.debug("Custom task types in workspace:")
                for item in custom_items:
                    LOG.debug("  [%s] %s", item.get("id"), item.get("name"))
            else:
                LOG.debug("No custom task types found in workspace.")
            for item in custom_items:
                if item.get("name", "").strip().lower() == "release":
                    self._release_type_id = int(item["id"])
                    LOG.debug("Release custom_item_id resolved to %s", self._release_type_id)
                    return self._release_type_id  # type: ignore[return-value]
            LOG.debug("No 'Release' custom task type found in workspace.")
            self._release_type_id = None
        except Exception:
            LOG.exception("Failed to fetch custom task types; Release expansion disabled.")
            self._release_type_id = None

        return self._release_type_id  # type: ignore[return-value]

    def _fetch_subtasks(self, parent_task_id: str) -> list[dict]:
        """
        Fetch direct subtasks of a task via GET /team/{team_id}/task?parent={id}.

        Returns a list of raw task dicts. Raises on API error.
        """
        team_id = self._get_team_id()
        if not team_id:
            return []
        response = self._get_client().make_request(
            method="GET",
            route=f"team/{team_id}/task",
            params={"parent": parent_task_id},
        )
        response_data: dict = response or {}  # type: ignore[assignment]
        return response_data.get("tasks", [])

    def get_relevant_issues(self, list_ids: list[str]) -> list[dict]:
        """
        Fetch open tasks from all given ClickUp list IDs.

        Tasks with terminal statuses (done, closed, complete, completed) are
        excluded. Results are deduplicated by task ID in case the same task
        appears in multiple lists.

        Tasks are returned grouped by list (i.e. all tasks from the first list,
        then all from the second, etc.).

        Args:
            list_ids: List of ClickUp list ID strings to fetch tasks from.

        Returns:
            Deduplicated list of dicts with keys:
              "id"        (str) – ClickUp task ID
              "name"      (str) – task name
              "list_name" (str) – name of the ClickUp list the task came from
            in the order they were encountered across lists.
        """
        from clickup_python_sdk.clickupobjects.list import List as CUList

        self._get_client()  # ensure the SDK singleton is initialised
        release_type_id = self._get_release_type_id()
        seen_ids: set[str] = set()
        result: list[dict] = []

        for list_id in list_ids:
            try:
                cu_list = CUList(id=list_id)
                cu_list.get()  # populates list metadata, including "name"
                list_name: str = cu_list["name"] if "name" in cu_list else list_id
                tasks = cu_list.get_tasks(
                    params={"subtasks": "false", "include_closed": "false"}
                )
                LOG.debug("List '%s' (%s): fetched %d task(s)", list_name, list_id, len(tasks))
                skipped = 0
                release_expanded = 0
                for task in tasks:
                    status = task["status"]["status"].lower()
                    if status in TERMINAL_STATUSES:
                        skipped += 1
                        continue

                    task_id = task["id"]
                    custom_item_id = task._data.get("custom_item_id")

                    # Release tasks: expand into direct subtasks instead.
                    if (
                        release_type_id is not None
                        and custom_item_id == release_type_id
                    ):
                        try:
                            subtasks = self._fetch_subtasks(task_id)
                            added = 0
                            for subtask in subtasks:
                                sub_status = subtask["status"]["status"].lower()
                                if sub_status in TERMINAL_STATUSES:
                                    continue
                                sub_id = subtask["id"]
                                if sub_id in seen_ids:
                                    continue
                                seen_ids.add(sub_id)
                                result.append(
                                    {
                                        "id": sub_id,
                                        "name": subtask["name"],
                                        "list_name": list_name,
                                    }
                                )
                                added += 1
                            LOG.debug(
                                "  Release task '%s' (%s): expanded into %d subtask(s)",
                                task["name"],
                                task_id,
                                added,
                            )
                            release_expanded += 1
                        except Exception:
                            LOG.exception(
                                "Failed to fetch subtasks for Release task %s", task_id
                            )
                        continue  # do not include the Release task itself

                    if task_id in seen_ids:
                        continue
                    seen_ids.add(task_id)
                    result.append(
                        {"id": task_id, "name": task["name"], "list_name": list_name}
                    )
                LOG.debug(
                    "  Skipped %d terminal task(s), expanded %d Release task(s)",
                    skipped,
                    release_expanded,
                )
            except Exception:
                LOG.exception("Failed to fetch tasks from list %s", list_id)

        return result

    def submit_time_registration(
        self, issue_id: str, decimal_hours: float
    ) -> None:
        """
        Track time on the given ClickUp task.

        Args:
            issue_id: ClickUp task ID string.
            decimal_hours: Time spent expressed as decimal hours (e.g. 1.5 = 90 min).
        """
        LOG.debug(
            "Submitting time registration: task=%s, decimal_hours=%s",
            issue_id,
            decimal_hours,
        )
        self._get_client()  # ensure the SDK singleton is initialised
        milliseconds = int(decimal_hours * _DECIMAL_HOURS_TO_MS)
        task = Task(id=issue_id)
        task.track_time(time=milliseconds)
        LOG.debug("Time registration submitted.")

    def get_workspace_tree(self) -> list[dict]:
        """
        Return the full space/folder/list hierarchy for the first workspace.

        This performs multiple API round trips and should be called from a
        background thread.

        Returns:
            List of space dicts with shape:
            [
              {
                "id": str, "name": str,
                "folders": [
                  {"id": str, "name": str, "lists": [{"id": str, "name": str}]}
                ],
                "lists": [{"id": str, "name": str}]   # folderless lists
              }
            ]
        """
        teams = self._get_client().get_teams()
        if not teams:
            return []
        team = teams[0]

        spaces_result = []
        for space in team.get_spaces():
            space_entry: dict = {
                "id": space["id"],
                "name": space["name"],
                "folders": [],
                "lists": [],
            }

            # Folderless lists directly in the space
            try:
                for lst in space.get_lists():
                    space_entry["lists"].append(
                        {"id": lst["id"], "name": lst["name"]}
                    )
            except Exception:
                LOG.exception(
                    "Failed to fetch folderless lists for space %s", space["id"]
                )

            # Folders and their lists
            try:
                for folder in space.get_folders():
                    folder_entry: dict = {
                        "id": folder["id"],
                        "name": folder["name"],
                        "lists": [],
                    }
                    try:
                        for lst in folder.get_lists():
                            folder_entry["lists"].append(
                                {"id": lst["id"], "name": lst["name"]}
                            )
                    except Exception:
                        LOG.exception(
                            "Failed to fetch lists for folder %s", folder["id"]
                        )
                    space_entry["folders"].append(folder_entry)
            except Exception:
                LOG.exception(
                    "Failed to fetch folders for space %s", space["id"]
                )

            spaces_result.append(space_entry)

        return spaces_result


# ----------------------------------------------------------------------
# Standalone test entry point
# ----------------------------------------------------------------------

if __name__ == "__main__":
    from zup.config_store import ConfigStore

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)-8s %(name)s: %(message)s",
    )
    LOG.setLevel(logging.DEBUG)

    _store = ConfigStore()
    token = _store.get("clickup_token")
    if not token:
        raise SystemExit(
            "No ClickUp token configured. Set it via the Zup settings dialog."
        )

    list_ids: list[str] = _store.get("clickup_lists", [])
    if not list_ids:
        raise SystemExit(
            "No ClickUp lists configured. Add lists via the Zup settings dialog."
        )

    client = ClickUpClient(user_token=token)
    issues = client.get_relevant_issues(list_ids)

    LOG.info("Found %d open issue(s):", len(issues))
    for issue in issues:
        LOG.info("  [%s] %s  (%s)", issue["list_name"], issue["name"], issue["id"])
