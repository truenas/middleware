==================
FreeNAS 10 Roadmap
==================
Includes functional outline + Schedule
--------------------------------------

---------------
Accounts (*M1*)
---------------
- User / Group Create, Edit, Delete (local) in middlware, CLI and GUI

- Bind to Directory Service (Active Directory, LDAP, NIS, NT4)
  This will also require a unified code path for looking up data in directory services and a mechanism for
  setting the search order such that the order of local, AD, LDAP, NIS, NT4 can be explicit.

- Extended User Properties (UI preferences, avatar, etc) possibly with the ability to either store them on
  a Directory Service or, when that is not possible, create a "slave" record locally that augments the DS record
  transparently.  If the DS record is deleted or updated, the slave record will also need to either be deleted or
  marked inactive.

- Authentication:  Both local users and DS users should be able to log into FreeNAS, either via the GUI or via
  SSH (PAM plugin to talk to our Directory Services shim will be necessary).

  + Integration with passwd(1), chsh(1), chfn(1) and so on; commands like adduser will be deleted or shimmed.

  +  Privileges: For *M1*, the only privilege will be "admin" - all Users with Admin privilege will be able
     to access all features of the UI and CLI, as well as being able to sudo from ssh.

---------------------------
System (*M1* / *M2* / *M3*)
---------------------------
- Information (*M1*)
  This will show basic system status information (which can also be shown in various dashboard items, but this
  will put it all in one place).

- Side Menu (this will be an "always up" part of the UI).  Should allow, among other operations: (*M1*)

    + Debug (show Debug UI)
    + Power Off - Shutdown the system (power off)
    + Reboot
    + Save Config (export configuration database)
    
- Basic Configuration (*M2*)
    This will allow Hostname, Language, Timezone and other essentials to be set

- UI Configuration (*M2*)
    This will allow HTTP/HTTPS and other Web-UI specific settings to be configured, as well as the CLI and various
    remote access rights to be controlled such that access to the system can be granted to specific users, privilege
    levels or networks.

- Peering Configuration (*M3*)
    Allow arbitrary hosts / services to be peered with FreeNAS in the following roles:
      + Backup:  Select one or more backup providers (S3, Commvault, Tarsnap, etc) as read-only backup references for
	one or more datasets, using a specific schedule.
      + Active / Passive peer: Replication with option for Peer to become active and take over services for this node
	(datasets and services are also specified, with the peering handshake being more complex in the case of fail-over).
      + Active / Active peer: Clustering / Load sharing peer, with the ability to simultaneously share services.

- Alert Configuration (*M2*)
    We will make alerts far more configurable in FreeNAS 10.  It will be possible to configure alerts by category or by
    individual alert (starting with all of the existing alerts in FreeNAS 9.3 as guides) using an alert namespace, where
    every alert has a class, a name and a severity level.  A given alert (or class / severity level) will be able to be
    enabled/disabled as well as tied to a given alert delivery method:

  - Email
  - UI Alert
  - External alert system (pluggable)

- Logging configuration (*M2*)
  We will supply a full logging configuration UI for being able to set the triggering / severity and formatting
  of log messages.

-----------------
Networking (*M2*)
-----------------

- Interface Add / Edit / Delete UI
  - Also on Interface Edit UI will be ability to add / remove from a LAGG

  - CARP and LAGG (interface groups) will show up as virtual interfaces that can be brought up / down as well as having
    their types changed and memberships edited. It should be possible to do this from either side, however - the
    individual interfaces or the CARP/LAGG groups.

  - The overall notion will be that interfaces will be first class citizens from which attributes like LAGG / CARP / VLAN
    settings are easy to set without losing context.

  - Default route / DNS and other networking parameters will be settable from this UI, outside of the interface
    configuration.

--------------
Storage (*M3*)
--------------

- View Disks by attribute (allocated or unallocated to pool(s))
- Zpool Create / Edit / Delete (with or without encryption)
- Dataset Create / Edit / Delete / Share (filesystem or zvol)
  + Share creation for dataset
  + iSCSI export of zvol
- Ability to select snapshot / backup / replication schedule for dataset or pool

---------------
Services (*M3*)
---------------
- Configure / Enable / Disable services
- See list of all Shares / Edit shares
- Set access policies for services

--------------
Plugins (*M4*)
--------------

- Browse / Add / Delete / Configure Plugins
  Based on AppCafe from PC-BSD, plugins will live in either Jails or VMs.  There should be a unified configuration
  mechanism that works in either scenario.
- Plugin creator API / SDK
  We should finally clarify what is required to create a plugin and how it interacts with the main UI, preferably
  via an extensible protocol that will also allow the UI to be template-driven, so new plugins can be easily
  created by simply obeying some straight-forward packaging rules and creating an XML/JSON/... UI template that
  automatically instantiates the appropriate UI and does the callback tie-ups.

-----------------
Jails/ VMS (*M4*)
-----------------

- We will provide full lifecycle management for Jails and also possibly
  Bhyve VMs, if BHyve can be made to work adequately in FreeNAS 10.
  For Jails, we will support:

+ Create / Delete / Configure / Clone / Update / Migrate

    We will support not just the creation and configuration of Jails in 10,
    but also allow them to be updated (a very frequently requested item)
    using some sort of package management scheme (we will have to constitute
    jails from packages).  We will also support the migration of Jails from
    one host to another using snapshotting / send / receive and metadata
    syncing.

+ Storage Management.  Similar to what we provide today, we will allow
  portions of the FreeNAS pool to be mapped into Jail space, though we may
  also choose to allow Jails to consume shares via the loopback device, where
  better coordination is required.

- For VMs, we will provide basic Create / Delete / Configure / Migrate
  functionality as well as:
  + ISO attach / detach
  + Attach to shares via local loopback
  + Console (maybe)
