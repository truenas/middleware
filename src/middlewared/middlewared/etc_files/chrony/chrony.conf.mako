# Welcome to the chrony configuration file. See chrony.conf(5) for more
# information about usable directives.

# Include configuration files found in /etc/chrony/conf.d.
confdir /etc/chrony/conf.d

# Use Debian vendor zone.
# pool 2.debian.pool.ntp.org iburst
<%
	ntp_query = middleware.call_sync('system.ntpserver.query')
%>\
% for ntp in ntp_query:
server ${ntp['address']}\
	% if ntp['burst']:
 burst\
	% endif
	% if ntp['iburst']:
 iburst\
	% endif
	% if ntp['prefer']:
 prefer\
	% endif
	% if ntp['maxpoll']:
 maxpoll ${ntp['maxpoll']}\
	% endif
	% if ntp['minpoll']:
 minpoll ${ntp['minpoll']}\
	% endif

% endfor

# Use time sources from DHCP.
sourcedir /run/chrony-dhcp

# Use NTP sources found in /etc/chrony/sources.d.
sourcedir /etc/chrony/sources.d

# This directive specify the location of the file containing ID/key pairs for
# NTP authentication.
keyfile /etc/chrony/chrony.keys

# This directive specify the file into which chronyd will store the rate
# information.
driftfile /var/lib/chrony/chrony.drift

# Save NTS keys and cookies.
ntsdumpdir /var/lib/chrony

# Uncomment the following line to turn logging on.
#log tracking measurements statistics

# Log files location.
logdir /var/log/chrony

# Stop bad estimates upsetting machine clock.
maxupdateskew 100.0

# This directive enables kernel synchronisation (every 11 minutes) of the
# real-time clock. Note that it can't be used along with the 'rtcfile' directive.
rtcsync

# Step the system clock instead of slewing it if the adjustment is larger than
# one second, but only in the first three clock updates.
makestep 1 3

# Get TAI-UTC offset and leap seconds from the system tz database.
# This directive must be commented out when using time sources serving
# leap-smeared time.
leapsectz right/UTC

% if ntp_query:
# Allow NTP client access from local network.
allow 127.0.0.1
allow ::1
allow 127.127.1.0
% endif
