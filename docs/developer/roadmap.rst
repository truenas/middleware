==================
FreeNAS 10 Roadmap
==================

FreeNAS 10 M3
-------------

- Deploy the FreeNAS 10 Developer blog
  `dev.freenas.org <http://dev.freenas.org>`__
- Scheduling Tab

  * Formerly known as "Tasks"
  * This should be where you see scheduled scrubs, replications, daily emails,
    etc.
  * Use a calendar icon.
- UPS
- dynamic DNS
- Support Tab (not fully spec'd out)

  * Telemetry?
  * Bug reports?
- Logs

  * Errors
  * Events
  * Completed, failed, and ongoing tasks
  * Combine with reporting?
- Per-user preferences and permissions (to a basic degree)

FreeNAS 10 M4
-------------

- Peering Configuration

  * Allow arbitrary hosts / services to be peered with FreeNAS in the following roles:

    + Backup:  Select one or more backup providers (S3, Commvault, Tarsnap,
      etc.) as read-only backup references for one or more datasets, using a
      specific schedule.
    + Active / Passive peer: Replication with option for Peer to become active
      and take over services for this node
    + (datasets and services are also specified, with the peering handshake
      being more complex in the case of fail-over).
      - Active / Active peer: Clustering / Load sharing peer, with the ability
      to simultaneously share services.

- AppCafe

  * Jail-based app system
  * base development instance on github, forked to create new apps.
  * Manual Jail creation will probably not be brought back in this milestone;
    see FreeNAS 10 SU
  * iX will provide signed and well tested jails for the most needed or
    ix-relevant apps
  * user contibuted apps will be scraped from github and have no signing

- Proactive Remidiation

  * As an expansion to the telemetry, add the ability for iX to respond to
    automatically reported issues before customers file support tickets. TrueNAS
    feature.

FreeNAS 10 M5
-------------

- Polish only as much as possible.
- Final triage as to what blocks RELEASE and what gets pushed to SUs.

FreeNAS 10 SU - Post 10.0 RELEASE features
------------------------------------------

- bhyve

  * Possible basis for using FreeNAS as part of a compute cluster, not just
    as storage.
  * Allows use of virtualized Linux, replacing the inferior functionality of
    Linux jails.
  * Replaces arbitrary jails, which we conflated with the plugin system in 9.x.

- Jails UI

  * Once apps and basic functionality aimed at the majority of our user
    community are working, bring back completely custom jails.
  * Full GUI controls: create, delete, start, stop, configure, migrate, and
    update.
