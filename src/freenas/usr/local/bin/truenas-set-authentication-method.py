#!/usr/bin/env python3
import json
import os
import shutil
import sys

import sqlite3

from middlewared.plugins.account import crypted_password
from middlewared.utils.db import FREENAS_DATABASE

if __name__ == "__main__":
    authentication_method = json.loads(sys.stdin.read())
    username = authentication_method["username"]
    password = crypted_password(authentication_method["password"])

    conn = sqlite3.connect(FREENAS_DATABASE)
    conn.row_factory = sqlite3.Row

    c = conn.cursor()
    if username == "root":
        c.execute("UPDATE account_bsdusers SET bsdusr_unixhash = ? WHERE bsdusr_username = 'root'", (password,))
    else:
        home = f"/home/{username}"

        c.execute("""
            INSERT INTO account_bsdgroups (bsdgrp_gid, bsdgrp_group, bsdgrp_builtin, bsdgrp_sudo, bsdgrp_smb,
                                           bsdgrp_sudo_commands, bsdgrp_sudo_nopasswd)
            VALUES (1000, ?, 0, 0, 0, '[]', 0)
        """, (username,))

        c.execute("SELECT last_insert_rowid()")
        group_id = dict(c.fetchone())["last_insert_rowid()"]

        c.execute("SELECT * FROM account_bsdusers WHERE bsdusr_username = 'root'")
        user = dict(c.fetchone())

        del user["id"]
        user["bsdusr_uid"] = 1000
        user["bsdusr_username"] = username
        user["bsdusr_unixhash"] = password
        user["bsdusr_home"] = home
        user["bsdusr_full_name"] = "Local Administrator"
        user["bsdusr_builtin"] = 0
        user["bsdusr_sudo"] = 1
        user["bsdusr_group_id"] = group_id
        c.execute(f"""
            INSERT INTO account_bsdusers ({', '.join([k for k in user.keys()])})
            VALUES ({', '.join(['?' for k in user.keys()])})
        """, tuple(user.values()))

        c.execute("SELECT last_insert_rowid()")
        user_id = dict(c.fetchone())["last_insert_rowid()"]

        c.execute("SELECT id FROM account_bsdgroups WHERE bsdgrp_group = 'builtin_administrators'")
        builtin_administrators_group_id = dict(c.fetchone())["id"]

        c.execute("""
            INSERT INTO account_bsdgroupmembership (bsdgrpmember_group_id, bsdgrpmember_user_id) VALUES (?, ?)
        """, (builtin_administrators_group_id, user_id))

        c.execute("UPDATE account_bsdusers SET bsdusr_password_disabled = 1 WHERE bsdusr_username = 'root'")

    conn.commit()
    conn.close()
