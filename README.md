# 'Zup for JIRA

This is a simple tool that pops up at given intervals and allows you to register
worktime into the users' open JIRA issues.

This tool is heavily inspired by a tool made by a former collegue of mine, 
Árni Þór Erlendsson, made, called [Task Reminder](http://www.sneddy.com/taskreminder/)

## Installation

I have not yet packaged this tool nor made any effort to freeze it (you can call this 
an Alpha-status of you want), so I suggest you clone this repository, fetch its
dependencies and run it from there:
```
git clone https://github.com/johannfr/zup.git
cd zup
poetry install --no-dev
poetry run python zup/zup.py
```

I have Python 3.8 installed and I haven't tested against other versions.

## Usage

Since its rather feature-limited (e.g. no settings, everything is hardcoded) the usage
is rather simple.

You will be prompted for the URL to your JIRA server, your username and your password.
URL and username are stored in a JSON-configuration file, while your password is stored
on your keyring (see: [keyring module](https://pypi.org/project/keyring/)).

### System tray icon

The application lives on your system tray. From there you can not choose to log work
instantly, but also exit the application! (woah!)

![zup-system-tray](https://user-images.githubusercontent.com/7012064/74829257-ef718d80-5310-11ea-95ba-7baadc3d7e31.png)

### Log-work-window

It's pretty self exlanatory. You get a list of open issues (any type: Task, Bug, Story,
Epic, whatever), a predefined list of durations and a "Register" button.

Since this window pops up periodically, you may not always be in a situation where you
want to be thinking about how much time you want to log to your issues, so there's a
snooze-button as well.

If you close this window using the window-managers window controls (i.e. the close-button)
the log-work-window will snooze for 15 minutes.

![zup-log-work-window](https://user-images.githubusercontent.com/7012064/74829251-ec769d00-5310-11ea-9068-d08425eff4a9.png)