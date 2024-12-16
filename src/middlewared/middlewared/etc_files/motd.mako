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

Warning: the supported mechanisms for making configuration changes
are the TrueNAS WebUI, CLI, and API exclusively. ALL OTHERS ARE
NOT SUPPORTED AND WILL RESULT IN UNDEFINED BEHAVIOR AND MAY
RESULT IN SYSTEM FAILURE.

% if motd:
${motd}
% endif
