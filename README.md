# 'Zup for TargetProcess

This is a simple tool that pops up at given (currently hard-coded) intervals and allows
you to register work-time into the your open TargetProcess issues.

This tool is heavily inspired by a tool made by a former colleague of mine made, 
Árni Þór Erlendsson, called [Task Reminder](http://www.sneddy.com/taskreminder/).

This tool was integrated with JIRA in a previous life, and that's where the (now outdated)
screenshots come from.

## Usage

Since its rather feature-limited (e.g. no settings, everything is hard-coded) the usage
is rather simple.

You will be prompted for the URL to your TargetProcess server, your username and your password.
URL and username are stored in a JSON-configuration file, while your password is stored
on your keyring (see: [keyring module](https://pypi.org/project/keyring/)).

### System tray icon

The application lives on your system tray. From there you can not only choose to log work
instantly, but also exit the application! (woah!)

![zup-system-tray](https://user-images.githubusercontent.com/7012064/74829257-ef718d80-5310-11ea-95ba-7baadc3d7e31.png)

### Log-work-window

It's pretty self explanatory. You get a list of open issues (any type: Task, Bug, Story,
Epic, whatever), a predefined list of durations and a "Register" button.

Since this window pops up periodically, you may not always be in a situation where you
want to be thinking about how much time you want to log to your issues, so there's a
snooze-button as well.

If you close this window using your window-managers' window-controls (e.g. the close-button)
the log-work-window will snooze for 15 minutes.

![zup-log-work-window](https://user-images.githubusercontent.com/7012064/74829251-ec769d00-5310-11ea-9068-d08425eff4a9.png)

