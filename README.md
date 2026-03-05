# Zup for ClickUp

A system-tray application that pops up at configurable intervals to prompt you to
log time against your ClickUp tasks. Tasks are fetched from one or more ClickUp
lists, grouped by list in the dropdown. Tasks of type Release are expanded into
their direct subtasks.

## Usage

### Setup

Open the settings dialog from the system-tray menu. Enter your ClickUp API token
and add the lists you want to pull tasks from.

### System tray icon

The application runs in the system tray. Right-clicking the icon gives you options
to log work, open settings, or quit.

![zup-system-tray](https://github.com/user-attachments/assets/e79aad1c-77fc-4afb-9355-ffdde0ac838c)

### Log-work window

The dropdown shows all non-terminal tasks from your configured lists. Each entry
is prefixed with the list name. Select a task, select a duration, and click
**Register**.

The window can be snoozed if you are not ready to log time. Closing it with the
window manager's close button also snoozes it for 15 minutes.

![zup-log-work-window](https://github.com/user-attachments/assets/a1ccf595-b1ad-459c-abd0-d3d8844d44e2)

### Settings window

- **ClickUp API token** — found under _ClickUp → Profile → Apps_.
- **ClickUp Lists** — the lists to pull tasks from. Use the **Add** button to
  browse your workspace and select lists.

![zup-log-settings-window](https://github.com/user-attachments/assets/7f6cce94-f2ae-447e-aca1-05d36aec5f05)

### List browser

Clicking **Add list...** in the settings window opens a tree view of your ClickUp
workspace, organised by space and folder. This list can take a **LONG** time to populate,
please be patient. Expand the nodes to find the lists you want and tick their checkbox and then press **OK**.

![zup-list-browser](foo.png)

## Credits

Inspired by [Task Reminder](http://www.sneddy.com/taskreminder/) by Árni Þór Erlendsson.
