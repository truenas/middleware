<%
    import random

    system_advanced = middleware.call_sync("system.advanced.config")
    resilver = middleware.call_sync("pool.resilver.config")
    boot_pool = middleware.call_sync("boot.pool_name")
%>\
SHELL=/bin/sh
PATH=/etc:/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin

30 3 * * * root midclt call dscache.refresh > /dev/null 2>&1
45 3 * * * root midclt call config.backup >/dev/null 2>&1

45 3 * * * root midclt call pool.scrub.run ${boot_pool} ${system_advanced['boot_scrub']} > /dev/null 2>&1

## Don't run these on TrueNAS HA standby controllers
## Redmine 55908
% if not middleware.call_sync("system.is_enterprise") or middleware.call_sync("failover.status") != "BACKUP":
    % for job in middleware.call_sync("cronjob.query", [["enabled", "=", True]]):
${' '.join(middleware.call_sync('cronjob.construct_cron_command', job["schedule"], "root", f"midclt call cronjob.run {job['id']} true"))}
    % endfor

    % for job in middleware.call_sync("rsynctask.query", [["enabled", "=", True]]):
<%
    if job["locked"]:
        middleware.call_sync('rsynctask.generate_locked_alert', job['id'])
        continue
%>\
${' '.join(middleware.call_sync('cronjob.construct_cron_command', job["schedule"], "root", f"midclt call rsynctask.run {job['id']}"))}
    % endfor

    % for job in middleware.call_sync("cloudsync.query", [["enabled", "=", True]]):
<%
    if job["locked"]:
        middleware.call_sync('cloudsync.generate_locked_alert', job['id'])
        continue
%>\
${' '.join(middleware.call_sync('cronjob.construct_cron_command', job["schedule"], "root", f"midclt call cloudsync.sync {job['id']}"))}
    % endfor

    % for job in middleware.call_sync("pool.scrub.query", [["enabled", "=", True]]):
${' '.join(middleware.call_sync('cronjob.construct_cron_command', job["schedule"], "root", f"midclt call pool.scrub.run {job['pool_name']} {job['threshold']}"))}
    % endfor

    % if resilver["enabled"]:
${resilver["begin"].split(":")[1]} ${resilver["begin"].split(":")[0]} * * * root \
        midclt call pool.configure_resilver_priority > /dev/null 2>&1

${resilver["end"].split(":")[1]} ${resilver["end"].split(":")[0]} * * * root \
        midclt call pool.configure_resilver_priority > /dev/null 2>&1
    % endif

    % if middleware.call_sync("datastore.query", "system.update", [["upd_autocheck", "=", True]]):
${random.randint(0, 59)} \
${random.randint(1, 4)} \
* * * root midclt call update.download > /dev/null 2>&1
    % endif

@weekly root update-smart-drivedb > /dev/null 2>&1
% endif
