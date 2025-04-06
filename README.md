# 'Zup for TargetProcess

This is a simple tool that pops up at given intervals and allows
you to register work-time into the your "Open" or "Test" TargetProcess UserStories.

This tool is heavily inspired by a tool made by a former colleague of mine made, 
Árni Þór Erlendsson, called [Task Reminder](http://www.sneddy.com/taskreminder/).

This tool was integrated with JIRA in a previous life, and that's where the (now outdated)
screenshots come from.

## Usage

First open up the settings dialog from the system-tray menu and enter the appropriate
information.

### System tray icon

The application lives on your system tray. From there you can log work right then,
open up the settings dialog and exit the application.

![zup-system-tray](https://github.com/user-attachments/assets/e79aad1c-77fc-4afb-9355-ffdde0ac838c)

### Log-work-window

It's pretty self explanatory. You get a list of UserStories that do NOT have "Done" as its state, a predefined list of durations and a "Register" button.

Since this window pops up periodically, you may not always be in a situation where you
want to be thinking about how much time you want to log to your issues, so there's a
snooze-button as well.

If you close this window using your window-managers' window-controls (e.g. the close-button)
the log-work-window will snooze for 15 minutes.

![zup-log-work-window](https://github.com/user-attachments/assets/a1ccf595-b1ad-459c-abd0-d3d8844d44e2)

### Settings window

Here you enter your settings. I hope this is self-explanatory.

![zup-log-settings-window](https://github.com/user-attachments/assets/36462d68-926b-4a6b-8cc2-21d0b6aa62f5)
