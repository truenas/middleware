import os

nologin = "/usr/sbin/nologin"


def is_valid_shell(shell):
    return os.path.exists(shell) and os.access(shell, os.X_OK)


def migrate(middleware):
    updated = False
    for user in middleware.call_sync("datastore.query", "account.bsdusers", [], {"prefix": "bsdusr_"}):
        if not user["shell"] or is_valid_shell(user["shell"]):
            continue

        new_shell = user["shell"].replace("/usr/local/", "/usr/")
        if not is_valid_shell(new_shell):
            if user["username"] == "root":
                new_shell = "/usr/bin/zsh"
            else:
                new_shell = nologin

        middleware.logger.info("Updating user %r shell from %r to %r", user["username"], user["shell"], new_shell)
        middleware.call_sync(
            "datastore.update", "account.bsdusers", user["id"], {"shell": new_shell}, {"prefix": "bsdusr_"}
        )
        updated = True

    if updated:
        middleware.call_sync("service.reload", "user")
