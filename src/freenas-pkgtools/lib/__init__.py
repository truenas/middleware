
# To use this:
# from . import Avatar
# os_type = Avatar()

# We may want to have more
# platform-specific stuff.

try:
    import sys
    sys.path.append("/usr/local/lib")
    from freenasUI.common.system import get_avatar_conf
    # Is there a way to this without hardcoding the key string?
    _os_type = get_avatar_conf()["AVATAR_PROJECT"]
except:
    _os_type = "FreeNAS"

def Avatar():
    return _os_type

