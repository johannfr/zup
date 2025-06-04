APPLICATION_NAME = "Zup"
APPLICATION_AUTHOR = "jof"
DEFAULT_TP_URL = "https://tern.tpondemand.com/"
DEFAULT_TP_TEAM_NAME = "Aces"
DEFAULT_TP_TAKE = 50
DEFAULT_TP_WHERE = (
    "(Team.Name eq '{team_name}')"
    "and(Assignable.EntityType.Name in ('Request', 'UserStory'))"
    "and(EntityState.Name ne 'Done')"
    "and(EntityState.Name ne 'Closed')"
)

DEFAULT_SCHEDULE_TYPE = "schedule"
DEFAULT_SCHEDULE_LIST = ["06:00", "11:00", "14:00"]
DEFAULT_INTERVAL_HOURS = 0
DEFAULT_INTERVAL_MINUTES = 15
