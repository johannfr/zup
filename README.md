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

The application lives on your system tray. From there you can not only choose to log work
instantly, but also exit the application! (woah!)

![zup-system-tray](https://user-images.githubusercontent.com/7012064/74829257-ef718d80-5310-11ea-95ba-7baadc3d7e31.png)

### Log-work-window

It's pretty self explanatory. You get a list of UserStories that have a status of either "Open" or "Test", a predefined list of durations and a "Register" button.

Since this window pops up periodically, you may not always be in a situation where you
want to be thinking about how much time you want to log to your issues, so there's a
snooze-button as well.

If you close this window using your window-managers' window-controls (e.g. the close-button)
the log-work-window will snooze for 15 minutes.

![zup-log-work-window](https://user-images.githubusercontent.com/7012064/74829251-ec769d00-5310-11ea-9068-d08425eff4a9.png)

