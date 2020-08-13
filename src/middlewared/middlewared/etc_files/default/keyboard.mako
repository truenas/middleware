<%
    layout = None
    variant = None
    config = middleware.call_sync("system.general.config")
    if config["kbdmap"] in middleware.call_sync("system.general.kbdmap_choices"):
        if "." in config["kbdmap"]:
            layout, variant = config["kbdmap"].split(".", 1)
        else:
            layout = config["kbdmap"]
            variant = ""
%>
# KEYBOARD CONFIGURATION FILE

# Consult the keyboard(5) manual page.

XKBMODEL="pc105"
% if layout and not (layout == "us" and variant == ""):
XKBLAYOUT="${layout},us"
XKBVARIANT="${variant},"
XKBOPTIONS="grp:alt_shift_toggle"
% else:
XKBLAYOUT="us"
XKBVARIANT=""
XKBOPTIONS=""
% endif

BACKSPACE="guess"
