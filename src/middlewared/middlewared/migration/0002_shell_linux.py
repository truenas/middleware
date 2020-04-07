# -*- coding=utf-8 -*-
import logging
import os

logger = logging.getLogger(__name__)


def migrate(middleware):
    updated = False
    for user in middleware.call_sync("datastore.query", "account.bsdusers", [], {"prefix": "bsdusr_"}):
        if user["shell"].startswith("/usr/local/") and not os.path.exists(user["shell"]):
            new_shell = user["shell"].replace("/usr/local/", "/usr/")
            if os.path.exists(new_shell) and os.access(new_shell, os.X_OK):
                logger.info("Updating user %r shell from %r to %r", user["username"], user["shell"], new_shell)
                middleware.call_sync(
                    "datastore.update",
                    "account.bsdusers",
                    user["id"],
                    {
                        "shell": new_shell,
                    },
                    {"prefix": "bsdusr_"},
                )
                updated = True

    if updated:
        middleware.call_sync("service.reload", "user")
