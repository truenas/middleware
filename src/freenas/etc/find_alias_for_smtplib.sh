#!/bin/sh
# We need to start the python script without stdout/stderr or it will
# segfault if the mail script chain is started from a process without tty.
# See #27994
exec `which python3` /etc/find_alias_for_smtplib.py "$@" > /dev/null 2>&1
