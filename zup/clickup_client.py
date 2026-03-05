"""
ClickUp client for fetching tasks from the "ISDS Releases" list.

Hierarchy navigated:
    team (first/only) -> space "Development" -> folder "ACES" -> list "ISDS Releases"

Only tasks with non-terminal statuses are returned (excludes done, closed, complete, etc.).
"""

from clickup_python_sdk.api import ClickupClient

SPACE_NAME = "Development"
FOLDER_NAME = "ACES"
LIST_NAME = "ISDS Releases"

TERMINAL_STATUSES = {"done", "closed", "complete", "completed"}


def get_isds_releases_tasks(user_token: str) -> list:
    """
    Fetch all open tasks (and subtasks) from the "ISDS Releases" list.

    Navigates: first team -> space "Development" -> folder "ACES" -> list "ISDS Releases".
    Tasks whose status is in TERMINAL_STATUSES are excluded.

    Args:
        user_token: ClickUp personal API token.

    Returns:
        List of Task objects with non-terminal statuses.

    Raises:
        ValueError: If the expected space, folder, or list cannot be found by name.
    """
    client = ClickupClient.init(user_token=user_token)

    teams = client.get_teams()
    if not teams:
        raise ValueError("No teams found for the provided token.")
    team = teams[0]

    spaces = team.get_spaces()
    space = next((s for s in spaces if s["name"] == SPACE_NAME), None)
    if space is None:
        available = [s["name"] for s in spaces]
        raise ValueError(
            f"Space '{SPACE_NAME}' not found. Available spaces: {available}"
        )

    folders = space.get_folders()
    folder = next((f for f in folders if f["name"] == FOLDER_NAME), None)
    if folder is None:
        available = [f["name"] for f in folders]
        raise ValueError(
            f"Folder '{FOLDER_NAME}' not found in space '{SPACE_NAME}'. "
            f"Available folders: {available}"
        )

    lists = folder.get_lists()
    task_list = next((l for l in lists if l["name"] == LIST_NAME), None)
    if task_list is None:
        available = [l["name"] for l in lists]
        raise ValueError(
            f"List '{LIST_NAME}' not found in folder '{FOLDER_NAME}'. "
            f"Available lists: {available}"
        )

    tasks = task_list.get_tasks(
        params={"subtasks": "true", "include_closed": "false"}
    )

    return [
        t for t in tasks
        if t["status"]["status"].lower() not in TERMINAL_STATUSES
    ]


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    token = os.environ.get("CLICKUP_TOKEN")
    if not token:
        raise SystemExit("CLICKUP_TOKEN environment variable is not set.")

    tasks = get_isds_releases_tasks(token)

    print(f"Found {len(tasks)} open task(s) in '{LIST_NAME}':\n")
    for task in tasks:
        parent = task["parent"] if "parent" in task else None
        indent = "  " if parent else ""
        status = task["status"]["status"]
        print(f"{indent}[{status}] {task['name']}  (id: {task['id']})")
