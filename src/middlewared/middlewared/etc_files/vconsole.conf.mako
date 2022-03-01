<%
    config = middleware.call_sync("system.general.config")
    layout = config["kbdmap"].split(".", 1)[0] or "us"
%>
# CONSOLE CONFIGURATION FILE
KEYMAP="${layout}"
