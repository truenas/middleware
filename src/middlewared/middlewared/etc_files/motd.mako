<%
	buildtime = middleware.call_sync('system.build_time')
	motd = middleware.call_sync('system.advanced.config')['motd']
%>\

	TrueNAS (c) 2009-${buildtime.year}, iXsystems, Inc.
	All rights reserved.
	TrueNAS code is released under the LGPLv3 and GPLv3 licenses with some
	source files copyrighted by (c) iXsystems, Inc. All other components
	are released under their own respective licenses.

	For more information, documentation, help or support, go here:
	http://truenas.com

% if motd:
${motd}
% endif
