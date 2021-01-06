<%
	if not middleware.call_sync('reporting.setup'):
		# Let's exit this if collectd related disk operations fail
		middleware.logger.error('Collectd configuration file could not be generated')
		return None

	reporting_config = middleware.call_sync('reporting.config')
	graphite = reporting_config['graphite']
	graphite_separateinstances = reporting_config['graphite_separateinstances']
	cpu_in_percentage = reporting_config['cpu_in_percentage']

	timespans = [3600, 86400, 604800, 2678400]
	if reporting_config['graph_age'] > 1:
	    if reporting_config['graph_age'] < 12:
	        timespans.append(reporting_config['graph_age'] * 2678400)
	    else:
	        timespans.append(31622400)
	        if reporting_config['graph_age'] > 12:
	            timespans.append(reporting_config['graph_age'] * 2678400)

	rra_rows = reporting_config['graph_points']

	base_dir = '/var/db/collectd'
	data_dir = '/var/db/collectd/rrd'
	network_config = middleware.call_sync('network.configuration.config')
	hostname = f"{network_config['hostname_local']}.{network_config['domain']}"

	if cpu_in_percentage:
		cpu_plugin_options = 'ValuesPercentage True'
		aggregation_plugin_cpu_type = 'percent'
	else:
		cpu_plugin_options = ''
		aggregation_plugin_cpu_type = 'cpu'

	ups_config = middleware.call_sync('ups.config')
	ups_service = middleware.call_sync('service.query', [['service', '=', 'ups']], {'get': True})

	has_internal_graphite_server = middleware.call_sync('reporting.has_internal_graphite_server')

	# TODO: NUT plugin has been disabled in upstream - https://salsa.debian.org/debian/pkg-collectd/-/blob/master/debian/changelog#L86
	# Let's bring it back once upstream brings it in

%>
Hostname "${hostname}"
BaseDir "${base_dir}"
PluginDir "/usr${"/local" if IS_FREEBSD else ""}/lib/collectd"

LoadPlugin aggregation
LoadPlugin cpu
LoadPlugin df
LoadPlugin disk
LoadPlugin exec
LoadPlugin interface
LoadPlugin load
LoadPlugin memory
LoadPlugin processes
LoadPlugin rrdcached
LoadPlugin swap
LoadPlugin uptime
LoadPlugin syslog
LoadPlugin threshold
LoadPlugin zfs_arc
LoadPlugin ${"nfsstat" if IS_FREEBSD else "nfs"}
LoadPlugin write_graphite
LoadPlugin python
% if IS_FREEBSD:
LoadPlugin cputemp
LoadPlugin ctl
LoadPlugin geom_stat
LoadPlugin nut
LoadPlugin zfs_arc_v2
% endif

% if IS_FREEBSD and (ups_service['state'] == 'RUNNING' or ups_service['enable']):
<Plugin "nut">
	UPS "${ups_config['complete_identifier']}"
</Plugin>
% endif
<Plugin "syslog">
	LogLevel err
</Plugin>

<Plugin "aggregation">
	<Aggregation>
		Plugin "cpu"
		Type "${aggregation_plugin_cpu_type}"
		GroupBy "Host"
		GroupBy "TypeInstance"
		CalculateNum false
		CalculateSum true
		CalculateAverage true
		CalculateMinimum false
		CalculateMaximum false
		CalculateStddev false
	</Aggregation>
</Plugin>
<Plugin cpu>
	${cpu_plugin_options}
</Plugin>
% if IS_FREEBSD:

<Plugin cputemp>
</Plugin>
% endif

<Plugin "disk">
% if IS_LINUX:
	Disk "/^disk/by-partuuid/"
% else:
	Disk "/^gptid/"
	Disk "/^md/"
	Disk "/^pass/"
% endif
	IgnoreSelected true
</Plugin>

<Plugin "exec">
	NotificationExec "nobody" "/usr/local/libexec/collectd_alert.py"
</Plugin>

<Plugin "interface">
% if IS_LINUX:
	Interface "lo"
% else:
	Interface "lo0"
	Interface "ipfw0"
	Interface "pflog0"
	Interface "pfsync0"
	Interface "plip0"
	Interface "/^usbus/"
% endif
	IgnoreSelected true
</Plugin>

<Plugin "rrdcached">
	DaemonAddress "unix:/var/run/rrdcached.sock"
	DataDir "${data_dir}"
	CreateFiles true

	RRARows ${rra_rows}
% for timespan in timespans:
	RRATimespan ${timespan}
% endfor
</Plugin>
% if IS_FREEBSD:

<Plugin "threshold">
	<Plugin "ctl">
		Instance "ha"
		<Type "disk_octets">
			WarningMax 10000000
			Persist true
			Interesting false
		</Type>
	</Plugin>
</Plugin>
% endif
# collectd 5.10 does not expect empty zfs_arc plugin block and marks it as wrong config
% if IS_FREEBSD:

<Plugin "zfs_arc">
</Plugin>

<Plugin "geom_stat">
	Filter "^([a]?da|ciss|md|mfi|md|nvd|pmem|xbd|vtbd)[0123456789]+$"
</Plugin>
% endif

<Plugin "df">
	Mountpoint "/^\/boot/"
	Mountpoint "/^\/var/db/system"
	FSType "tmpfs"
% if IS_LINUX:
	FSType "bindfs"
	FSType "devtmpfs"
% else:
	FSType "devfs"
	FSType "nullfs"
	FSType "fdescfs"
% endif
	IgnoreSelected true
	LogOnce true
</Plugin>

<Plugin python>
	ModulePath "/usr/local/lib/collectd_pyplugins"
	LogTraces true
	Interactive false
	Import "disktemp"

	<Module "disktemp">
	</Module>
</Plugin>

<Plugin "write_graphite">
% if has_internal_graphite_server:
    <Node "middleware">
        Host "localhost"
        Port "2003"
        Protocol "tcp"
        LogSendErrors true
        StoreRates true
        AlwaysAppendDS true
        EscapeCharacter "_"
    </Node>
% endif
% if graphite:
	<Node "graphite">
		Host "${graphite}"
		Port "2003"
		Protocol "tcp"
		LogSendErrors true
		Prefix "servers."
		Postfix ""
		StoreRates true
		AlwaysAppendDS false
		EscapeCharacter "_"
% if graphite_separateinstances:
		SeparateInstances true
% endif
	</Node>
% endif
</Plugin>
