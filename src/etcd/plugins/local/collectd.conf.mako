Hostname "localhost"
FQDNLookup true
BaseDir "/var/db/collectd"
PIDFile "/var/run/collectd.pid"
PluginDir "/usr/local/lib/collectd"

LoadPlugin aggregation
LoadPlugin cpu
LoadPlugin df
LoadPlugin disk
LoadPlugin interface
LoadPlugin load
LoadPlugin memory
LoadPlugin network
LoadPlugin processes
LoadPlugin swap
LoadPlugin uptime
LoadPlugin syslog
LoadPlugin zfs_arc
LoadPlugin python
LoadPlugin unixsock
LoadPlugin write_graphite

<Plugin "syslog">
    LogLevel err
</Plugin>

<Plugin "aggregation">
    <Aggregation>
        Plugin "cpu"
        Type "cpu"
        GroupBy "Host"
        GroupBy "TypeInstance"
        CalculateSum true
    </Aggregation>
</Plugin>

<Plugin "interface">
    Interface "lo0"
    Interface "plip0"
    Interface "/^usbus/"
    IgnoreSelected true
</Plugin>

<Plugin "disk">
    Disk "/^gptid/"
    Disk "/^md/"
    Disk "/^pass/"
    IgnoreSelected true
</Plugin>

<Plugin "zfs_arc">
</Plugin>

<Plugin "df">
</Plugin>

<Plugin unixsock>
    SocketFile "/var/run/collectd.sock"
    SocketGroup "collectd"
    SocketPerms "0770"
</Plugin>

<Plugin "write_graphite">
    <Node "freenas">
        Host "localhost"
        Port "2003"
        StoreRates true
        AlwaysAppendDS true
   </Node>
</Plugin>
