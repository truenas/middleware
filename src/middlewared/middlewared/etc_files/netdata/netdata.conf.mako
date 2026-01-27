<%
    from middlewared.plugins.reporting.netdata.utils import NETDATA_PORT, NETDATA_UPDATE_EVERY

    netdata_cache_dataset = middleware.call_sync('reporting.netdata_storage_location')
    netdata_state_location =  middleware.call_sync('reporting.netdata_state_location')
    if not netdata_cache_dataset:
        # Let's exit if netdata storage is not in place
        middleware.logger.error('Netdata configuration file could not be generated')
        raise FileShouldNotExist()

    reporting_config = middleware.call_sync('reporting.config')
    disk_space_for_tier0 = middleware.call_sync('netdata.get_disk_space_for_tier0')
    disk_space_for_tier1 = middleware.call_sync('netdata.get_disk_space_for_tier1')

%>\
[global]
	run as user = netdata
	web files owner = root
	web files group = root
	# Netdata is not designed to be exposed to potentially hostile
	# networks. See https://github.com/netdata/netdata/issues/164
	bind socket to IP = 127.0.0.1:${NETDATA_PORT}
	update_every = ${NETDATA_UPDATE_EVERY}

[db]
	mode = dbengine
	storage tiers = 2
	dbengine multihost disk space MB = ${disk_space_for_tier0}

	dbengine tier 1 multihost disk space MB = ${disk_space_for_tier1}
	dbengine tier 1 update every iterations = ${reporting_config['tier1_update_interval']}

[directories]
    cache = ${netdata_cache_dataset}
    home = ${netdata_cache_dataset}
    lib = ${netdata_state_location}

[logs]
	access = off

[plugins]
	debugfs = no
	ebpf = no
	systemd-journal = no
	network-viewer = no
	proc = yes
	diskspace = no
	cgroups = yes
	tc = no
	idlejitter = no
	perf = no
	apps = no
	nfacct = no
	netdata monitoring = no # We want to disable netdata's agent stats

[web]
	enabled = no

[health]
	enabled = no

[statsd]
	enabled = no

[plugin:proc]
	netdata server resources = yes
	/proc/diskstats = no
	/proc/meminfo = no
	/proc/net/dev = yes
	/proc/pagetypeinfo = no
	/proc/stat = no
	/proc/uptime = yes
	/proc/loadavg = yes
	/proc/sys/kernel/random/entropy_avail = no
	/proc/pressure = no
	/proc/interrupts = no
	/proc/softirqs = no
	/proc/vmstat = no
	/sys/kernel/mm/ksm = no
	/sys/block/zram = no
	/sys/devices/system/edac/mc = no
	/sys/devices/system/node = no
	/proc/net/wireless = no
	/proc/net/sockstat = no
	/proc/net/sockstat6 = no
	/proc/net/netstat = no
	/proc/net/snmp = no
	/proc/net/snmp6 = no
	/proc/net/sctp/snmp = no
	/proc/net/softnet_stat = no
	/proc/net/ip_vs/stats = no
	/sys/class/infiniband = no
	/proc/net/stat/conntrack = no
	/proc/net/stat/synproxy = no
	/proc/mdstat = no
	/proc/net/rpc/nfsd = yes
	/proc/net/rpc/nfs = yes
	/proc/spl/kstat/zfs/arcstats = no
	/proc/spl/kstat/zfs/pool/state = no
	/sys/fs/btrfs = no
	ipc = no
	/sys/class/power_supply = no

[plugin:proc:/proc/net/dev]
	filename to monitor = /proc/net/dev
	path to get virtual interfaces = /sys/devices/virtual/net/%s
	path to get net device speed = /sys/class/net/%s/speed
	path to get net device duplex = /sys/class/net/%s/duplex
	path to get net device operstate = /sys/class/net/%s/operstate
	enable new interfaces detected at runtime = auto
	bandwidth for all interfaces = auto
	packets for all interfaces = auto
	errors for all interfaces = auto
	drops for all interfaces = auto
	fifo for all interfaces = no
	compressed packets for all interfaces = auto
	frames, collisions, carrier counters for all interfaces = auto
	disable by default interfaces matching = lo fireqos* *-ifb veth*
	refresh interface speed every seconds = 1
	refresh interface duplex every seconds = 1
	refresh interface operstate every seconds = 1

[plugin:cgroups]
        enable by default cgroups names matching = !*udev* *
