<%
    config = render_ctx['system.general.config']
    layout = config["kbdmap"].split(".", 1)[0]
%>
# CONSOLE CONFIGURATION FILE
KEYMAP="${layout}"
