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
% if ntp_query:
restrict default ignore
restrict -6 default ignore
restrict 127.0.0.1
restrict -6 ::1
restrict 127.127.1.0
% for ntp in ntp_query:
restrict ${ntp['address']} nomodify notrap nopeer noquery
% endfor
% endif
