#!/bin/sh

# Some tests require X in order to run.
# For example some tests pop up a Firefox web browser.
# In order to run these tests "headless", we
# spawn Xvfb, which is a headless X server, and set the
# DISPLAY variable to point to that server.
# We then invoke the program.
# This allows some of these tests to run "headless" in an automation
# environment.


type Xvfb
if [ $? -ne 0 ]; then
   echo "Xvfb not found."
   echo "Try installing:  pkg install x11-servers/xorg-vfbserver"
   exit 1
fi

if [ $# -lt 1 ]; then
   echo "Usage:"
   echo "   $0 [command]"
   echo ""
   echo "   Example:  $0 python test-upgrade-gui-001.py -f ../config/config-craig.json"
   exit 1
fi

set -x
Xvfb :99 -ac  &

sleep 5
 
# environment variable to let X applications
# such as Firefox know where to display
export DISPLAY=:99

$@
STATUS=$?

sleep 3

killall Xvfb

exit $STATUS
