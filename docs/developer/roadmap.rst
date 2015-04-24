==================
FreeNAS 10 Roadmap
==================
Includes functional outline + Schedule
--------------------------------------

- Peering Configuration (*M3*)
    Allow arbitrary hosts / services to be peered with FreeNAS in the following roles:
      + Backup:  Select one or more backup providers (S3, Commvault, Tarsnap, etc) as read-only backup references for
	one or more datasets, using a specific schedule.
      + Active / Passive peer: Replication with option for Peer to become active and take over services for this node
	(datasets and services are also specified, with the peering handshake being more complex in the case of fail-over).
      + Active / Active peer: Clustering / Load sharing peer, with the ability to simultaneously share services.


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
