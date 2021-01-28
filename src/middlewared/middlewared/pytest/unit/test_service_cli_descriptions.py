import textwrap

import pytest

from middlewared.service import CoreService


@pytest.mark.parametrize("doc,names,descriptions", [
    (
        textwrap.dedent("""\
            Create a new user.

            If `uid` is not provided it is automatically filled with the next one available.

            `group` is required if `group_create` is false.

            Available choices for `shell` can be retrieved with `user.shell_choices`.

            `smb` specifies whether the user should be allowed access to SMB shares. User
            will also automatically be added to the `builtin_users` group.
        """),
        {"uid", "group", "group_create", "shell", "smb"},
        {
            "uid": "If `uid` is not provided it is automatically filled with the next one available.",
            "group": "`group` is required if `group_create` is false.",
            "group_create": "`group` is required if `group_create` is false.",
            "shell": "Available choices for `shell` can be retrieved with `user.shell_choices`.",
            "smb": "`smb` specifies whether the user should be allowed access to SMB shares. User\n"
                   "will also automatically be added to the `builtin_users` group.",
        }
    ),
    (
        textwrap.dedent("""\
            * `schedule` is a schedule to run replication task. Only `auto` replication tasks without bound periodic
              snapshot tasks can have a schedule
            * `restrict_schedule` restricts when replication task with bound periodic snapshot tasks runs. For example,
              you can have periodic snapshot tasks that run every 15 minutes, but only run replication task every hour.
            * Enabling `only_matching_schedule` will only replicate snapshots that match `schedule` or
              `restrict_schedule`
            * `allow_from_scratch` will destroy all snapshots on target side and replicate everything from scratch if none
              of the snapshots on target side matches source snapshots
            * `readonly` controls destination datasets readonly property:
              * `SET` will set all destination datasets to readonly=on after finishing the replication
              * `REQUIRE` will require all existing destination datasets to have readonly=on property
              * `IGNORE` will avoid this kind of behavior
            * `hold_pending_snapshots` will prevent source snapshots from being deleted by retention of replication fails
              for some reason
        """),
        {"schedule", "restrict_schedule", "only_matching_schedule", "allow_from_scratch", "readonly", "hold_pending_snapshots", "auto"},
        {
            "schedule": "* `schedule` is a schedule to run replication task. Only `auto` replication tasks without bound periodic\n"
                        "  snapshot tasks can have a schedule\n"
                        "* Enabling `only_matching_schedule` will only replicate snapshots that match `schedule` or\n"
                        "  `restrict_schedule`",
            "restrict_schedule": "* `restrict_schedule` restricts when replication task with bound periodic snapshot tasks runs. For example,\n"
                                 "  you can have periodic snapshot tasks that run every 15 minutes, but only run replication task every hour.\n"
                                "* Enabling `only_matching_schedule` will only replicate snapshots that match `schedule` or\n"
                                "  `restrict_schedule`",
            "only_matching_schedule": "* Enabling `only_matching_schedule` will only replicate snapshots that match `schedule` or\n"
                                      "  `restrict_schedule`",
            "allow_from_scratch": "* `allow_from_scratch` will destroy all snapshots on target side and replicate everything from scratch if none\n"
                                  "  of the snapshots on target side matches source snapshots",
            "readonly": "* `readonly` controls destination datasets readonly property:\n"
                        "  * `SET` will set all destination datasets to readonly=on after finishing the replication\n"
                        "  * `REQUIRE` will require all existing destination datasets to have readonly=on property\n"
                        "  * `IGNORE` will avoid this kind of behavior",
            "hold_pending_snapshots": "* `hold_pending_snapshots` will prevent source snapshots from being deleted by retention of replication fails\n"
                                      "  for some reason",
            "auto": "* `schedule` is a schedule to run replication task. Only `auto` replication tasks without bound periodic\n"
                    "  snapshot tasks can have a schedule",
        },
    )
])
def test_cli_args_descriptions(doc, names, descriptions):
    assert CoreService(None)._cli_args_descriptions(doc, names) == descriptions
