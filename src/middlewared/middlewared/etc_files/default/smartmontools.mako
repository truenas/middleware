<%
    config = middleware.call_sync("smart.config")
%>
# Defaults for smartmontools initscript (/etc/init.d/smartmontools)
# This is a POSIX shell fragment

# List of devices you want to explicitly enable S.M.A.R.T. for
# Not needed (and not recommended) if the device is monitored by smartd
#enable_smart="/dev/hda /dev/hdb"

# uncomment to pass additional options to smartd on startup
smartd_opts="--interval=${config["interval"] * 60} -q nodev"
