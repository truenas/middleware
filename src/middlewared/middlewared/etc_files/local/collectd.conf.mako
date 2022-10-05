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
	hostname = middleware.call_sync('reporting.hostname')

	if cpu_in_percentage:
		cpu_plugin_options = 'ValuesPercentage True'
		aggregation_plugin_cpu_type = 'percent'
	else:
		cpu_plugin_options = ''
		aggregation_plugin_cpu_type = 'cpu'

	has_internal_graphite_server = middleware.call_sync('reporting.has_internal_graphite_server')
%>
Hostname "${hostname}"
BaseDir "${base_dir}"
PluginDir "/usr/lib/collectd"
TypesDB "/usr/share/collectd/types.db"
TypesDB "/usr/share/collectd/types.db.truenas"

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
LoadPlugin write_graphite
LoadPlugin python

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
	Disk "/^disk/by-partuuid/"
	IgnoreSelected true
</Plugin>

<Plugin "exec">
	NotificationExec "nobody" "/usr/local/libexec/collectd_alert.py"
</Plugin>

<Plugin "interface">
	Interface "lo"
	Interface "lo0"
	Interface "ipfw0"
	Interface "pflog0"
	Interface "pfsync0"
	Interface "plip0"
	Interface "/^usbus/"
	Interface "/^veth/"
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
	Mountpoint "/^\/mnt\/[^/]+\/ix-applications/"
	Mountpoint "/^\/var\/db\/system/"
	Mountpoint "/^\/var\/lib\/kubelet/"
	Mountpoint "/\/\.zfs\/snapshot\//"
	FSType "tmpfs"
	FSType "bindfs"
	FSType "devtmpfs"
	FSType "devfs"
	FSType "nullfs"
	FSType "fdescfs"
	IgnoreSelected true
	LogOnce true
</Plugin>

<Plugin python>
	ModulePath "/usr/local/lib/collectd_pyplugins"
	LogTraces true
	Interactive false
	Import "cputemp"
	Import "disktemp"
	Import "nfsstat"

	<Module "cputemp">
	</Module>
	<Module "disktemp">
	</Module>
	<Module "nfsstat">
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

# Limit how much memory collectd can consume for its write queue when graphite host is down.
# Normal system has about 1500 metrics (most of them collected every 10 seconds).
# Hi-end system with 1000 drives and 1000 datasets will have about 10000 metrics.
WriteQueueLimitLow 50000
WriteQueueLimitHigh 50000
