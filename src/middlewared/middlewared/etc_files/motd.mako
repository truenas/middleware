<%
	buildtime = middleware.call_sync('system.build_time')
	motd = middleware.call_sync('system.advanced.config')['motd']
%>\
% if IS_FREEBSD:
FreeBSD ?.?.?  (UNKNOWN)
% endif

	TrueNAS (c) 2009-${buildtime.year}, iXsystems, Inc.
	All rights reserved.
	TrueNAS code is released under the modified BSD license with some
	files copyrighted by (c) iXsystems, Inc.

	For more information, documentation, help or support, go here:
	http://truenas.com
% if motd:
${motd}
% endif
