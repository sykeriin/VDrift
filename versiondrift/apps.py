"""App registry: env factory, task list, and the version pairs evaluated."""
def get(app: str):
    if app == "gitea":
        from .envs.gitea import GiteaEnv; from .tasks_gitea import TASKS
        return GiteaEnv, TASKS
    if app == "nextcloud":
        from .envs.nextcloud import NextcloudEnv; from .tasks_nextcloud import TASKS
        return NextcloudEnv, TASKS
    raise KeyError(app)

PAIRS = {"gitea": [("1.17.4", "1.19.4"), ("1.19.4", "1.21.11"), ("1.21.11", "1.22.3"), ("1.17.4", "1.22.3")],
         "nextcloud": [("24", "25")]}
