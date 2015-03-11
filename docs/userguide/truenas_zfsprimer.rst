.. _ZFS Primer:

ZFS Primer
------------

ZFS is an advanced, modern filesystem that was specifically designed to provide features not available in traditional UNIX filesystems. It was originally
developed at Sun with the intent to open source the filesystem so that it could be ported to other operating systems. After the Oracle acquisition of Sun,
some of the original ZFS engineers founded
`OpenZFS <http://open-zfs.org>`_ in order to provided continued, collaborative development of the open source version. To differentiate itself from Oracle ZFS
version numbers, OpenZFS uses feature flags. Feature flags are used to tag features with unique names in order to provide portability between OpenZFS
implementations running on different platforms, as long as all of the feature flags enabled on the ZFS pool are supported by both platforms. TrueNAS® uses
OpenZFS and each new version of TrueNAS® keeps up-to-date with the latest feature flags and OpenZFS bug fixes.

Here is an overview of the features provided by ZFS:

**ZFS is a transactional, Copy-On-Write**
`(COW) <https://en.wikipedia.org/wiki/ZFS#Copy-on-write_transactional_model>`_ filesystem. For each write request, a copy is made of the associated disk
block(s) and all changes are made to the copy rather than to the original block(s). Once the write is complete, all block pointers are changed to point to the
new copy. This means that ZFS always writes to free space and most writes will be sequential. When ZFS has direct access to disks, it will bundle multiple
read and write requests into transactions; most filesystems can not do this as they only have access to disk blocks. A transaction either completes or fails,
meaning there will never be a
`write-hole <http://blogs.oracle.com/bonwick/entry/raid_z>`_  and a filesystem checker utility is not necessary. Because of the transactional design, as
additional storage capacity is added it becomes immediately available for writes; to rebalance the data, one can copy it to re-write the existing data across
all available disks. As a 128-bit filesystem, the maximum filesystem or file size is 16 exabytes.
  
**ZFS was designed to be a self-healing filesystem**. As ZFS writes data, it creates a checksum for each disk block it writes. As ZFS reads data, it validates
the checksum for each disk block it reads. If ZFS identifies a disk block checksum error on a pool that is mirrored or uses RAIDZ*, ZFS will fix the corrupted
data with the correct data. Since some disk blocks are rarely read, regular scrubs should be scheduled so that ZFS can read all of the data blocks in order to
validate their checksums and correct any corrupted blocks. While multiple disks are required in order to provide redundancy and data correction, ZFS will
still provide  data corruption detection to a system with one disk. TrueNAS® automatically schedules a monthly scrub for each ZFS pool and the results of the
scrub will be displayed in :ref:`View Volumes`. Reading the scrub results can provide an early indication of possible disk failure.
  
Unlike traditional UNIX filesystems, **you do not need to define partition sizes at filesystem creation time**. Instead, you feed a certain number of disk(s)
at a time (known as a vdev) to a ZFS pool and create filesystems from the pool as needed. As more capacity is needed, identical vdevs can be striped into the
pool. In TrueNAS®, :ref:`Volume Manager` can be used to create or extend ZFS pools. Once a pool is created, it can be divided into dynamically-sized
datasets or fixed-size zvols as needed. Datasets can be used to optimize storage for the type of data being stored as permissions and properties such as
quotas and compression can be set on a per-dataset level. A zvol is essentially a raw, virtual block device which can be used for applications that need
raw-device semantics such as iSCSI device extents.
  
**ZFS supports real-time data compression**. Compression happens when a block is written to disk, but only if the written data will benefit from compression.
When a compressed block is accessed, it is automatically decompressed. Since compression happens at the block level, not the file level, it is transparent to
any applications accessing the compressed data. By default, ZFS pools made using TrueNAS® version 9.2.1 or later will use the recommended LZ4 compression
algorithm.
  
**ZFS provides low-cost, instantaneous snapshots** of the specified pool, dataset, or zvol. Due to COW, the initial size of a snapshot is 0 bytes and the size
of the snapshot increases over time as changes to the files in the snapshot are written to disk. Snapshots can be used to provide a copy of data at the point
in time the snapshot was created. When a file is deleted, its disk blocks are added to the free list; however, the blocks for that file in any existing
snapshots are not added to the free list until all referencing snapshots are removed. This means that snapshots provide a clever way of keeping a history of
files, should you need to recover an older copy of a file or a deleted file. For this reason, many administrators take snapshots often (e.g. every 15
minutes), store them for a period of time (e.g. for a month), and store them on another system. Such a strategy allows the administrator to roll the system
back to a specific time or, if there is a catastrophic loss, an off-site snapshot can restore the system up to the last snapshot interval (e.g. within 15
minutes of the data loss). Snapshots are stored locally but can also be replicated to a remote ZFS pool. During replication, ZFS does not do a byte-for-byte
copy but instead converts a snapshot into a stream of data. This design means that the ZFS pool on the receiving end does not need to be identical and can use
a different RAIDZ level, volume size, compression settings, etc.
  
**ZFS boot environments provide a method for recovering from a failed upgrade**. Beginning with TrueNAS® version 9.3, a snapshot of the dataset the operating
system resides on is automatically taken before an upgrade or a system update. This saved boot environment is automatically added to the GRUB boot loader.
Should the upgrade or configuration change fail, simply reboot and select the previous boot environment from the boot menu. Users can also create their own
boot environments in :menuselection:`System --> Boot` as needed, for example before making configuration changes. This way, the system can be rebooted into
a snapshot of the system that did not include the new configuration changes.

**ZFS provides a write cache** in RAM as well as a
`ZFS Intent Log <http://blogs.oracle.com/realneel/entry/the_zfs_intent_log>`_ (ZIL). The ZIL is a temporary storage area for **synchronous** writes until they
are written asynchronously to the ZFS pool. If the system has many synchronous writes where the integrity of the write matters, such as from a database server
or when using NFS over ESXi, performance can be increased by adding a
dedicated log device, or slog, using :ref:`Volume Manager`.  More detailed explanations can be found in this
`forum post <http://forums.freenas.org/threads/some-insights-into-slog-zil-with-zfs-on-freenas.13633/>`_ and in this
`blog post <http://nex7.blogspot.com/2013/04/zfs-intent-log.html>`_. A dedicated log device will have no affect on CIFS, AFP, or iSCSI as these protocols
rarely use synchronous writes. When creating a dedicated log device, it is recommended to use a fast SSD with a supercapacitor or a bank of capacitors that
can handle writing the contents of the SSD's RAM to the SSD. The :command:`zilstat` utility can be run from Shell to help determine if the system would
benefit from a dedicated ZIL device. See
`this website <http://www.richardelling.com/Home/scripts-and-programs-1/zilstat>`_
for usage information. If you decide to create a dedicated log device to speed up NFS writes, the SSD can be half the size of system RAM as anything larger
than that is unused capacity. The log device does not need to be mirrored on a pool running ZFSv28 or feature flags as the system will revert to using the ZIL
if the log device fails and only the data in the device which had not been written to the pool will be lost (typically the last few seconds of writes). You
can replace the lost log device in the :menuselection:`View Volumes --> Volume Status` screen. Note that a dedicated log device can not be shared between ZFS
pools and that the same device cannot hold both a log and a cache device.

**ZFS provides a read cache** in RAM, known as the ARC, to reduce read latency. TrueNAS® adds ARC stats to 
`top(1) <http://www.freebsd.org/cgi/man.cgi?query=top>`_ and includes the :command:`arc_summary.py`
and :command:`arcstat.py` tools for monitoring the efficiency of the ARC. If an SSD is dedicated as a cache device, it is known as an
`L2ARC <https://blogs.oracle.com/brendan/entry/test>`_ and ZFS uses it to store more reads which can increase random read performance. However, adding an
L2ARC is **not** a substitute for insufficient RAM as L2ARC needs RAM in order to function.  If you do not have enough RAM for a good sized ARC, you will not
be increasing performance, and in most cases you will actually hurt performance and could potentially cause system instability. RAM is always faster than
disks, so always add as much RAM as possible before determining if the system would benefit from a L2ARC device. If you have a lot of applications that do
large amounts of **random** reads, on a dataset small enough to fit into the L2ARC, read performance may be increased by adding a dedicated cache device using
:ref:`Volume Manager`. SSD cache devices only help if your active data is larger than system RAM, but small enough that a significant percentage of it
will fit on the SSD. As a general rule of thumb, an L2ARC should not be added to a system with less than 64 GB of RAM and the size of an L2ARC should not
exceed 5x the amount of RAM. In some cases, it may be more efficient to have two separate pools: one on SSDs for active data and another on hard drives for
rarely used content. After adding an L2ARC, monitor its effectiveness using tools such as :command:`arcstat`. If you need to increase the size of an existing
L2ARC, you can stripe another cache device using :ref:`Volume Manager`. The GUI will always stripe L2ARC, not mirror it, as the contents of L2ARC are
recreated at boot. Losing an L2ARC device will not affect the integrity of the pool, but may have an impact on read performance, depending upon the workload
and the ratio of dataset size to cache size. Note that a dedicated L2ARC device can not be shared between ZFS pools. 

**ZFS was designed to provide redundancy while addressing some of the inherent limitations of hardware RAID** such as the write-hole and corrupt data written
over time before the hardware controller provides an alert. ZFS provides three levels of redundancy, known as RAIDZ*, where the number after the RAIDZ
indicates how many disks per vdev can be lost without losing data. ZFS also supports mirrors, with no restrictions on the number of disks in the mirror. ZFS
was designed for commodity disks so no RAID controller is needed. While ZFS can also be used with a RAID controller, it is recommended that the controller be
put into JBOD mode so that ZFS has full control of the disks. When determining the type of ZFS redundancy to use, consider whether your goal is to maximize
disk space or performance:

* RAIDZ1 maximizes disk space and generally performs well when data is written and read in large chunks (128K or more).

* RAIDZ2 offers better data availability and significantly better mean time to data loss (MTTDL) than RAIDZ1.

* A mirror consumes more disk space but generally performs better with small random reads. For better performance, a mirror is strongly favored over any 
  RAIDZ, particularly for large, uncacheable, random read loads.

* Using more than 12 disks per vdev is not recommended. The recommended number of disks per vdev is between 3 and 9. If you have more disks, use multiple
  vdevs.

* Some older ZFS documentation recommends that a certain number of disks is needed for each type of RAIDZ in order to achieve optimal performance. On systems
  using LZ4 compression, which is the default for TrueNAS® 9.2.1 and higher, this is no longer true. See
  `ZFS RAIDZ stripe width, or: How I Learned to Stop Worrying and Love RAIDZ <http://blog.delphix.com/matt/2014/06/06/zfs-stripe-width/>`_ for details.

.. warning:: NO RAID SOLUTION PROVIDES A REPLACEMENT FOR A RELIABLE BACKUP STRATEGY. BAD STUFF CAN STILL HAPPEN AND YOU WILL BE GLAD THAT YOU BACKED UP YOUR
   DATA WHEN IT DOES. See :ref:`Periodic Snapshot Tasks` and :ref:`Replication Tasks` if you would like to use replicated ZFS snapshots as part of your backup
   strategy.

While ZFS provides many benefits, there are some caveats to be aware of:

* At 90% capacity, ZFS switches from performance- to space-based optimization, which has massive performance implications. For maximum write performance and
  to prevent problems with drive replacement, add more capacity before a pool reaches 80%. If you are using iSCSI, it is recommended to not let the pool go
  over 50% capacity to prevent fragmentation issues.
  
* When considering the number of disks to use per vdev, consider the size of the disks and the amount of time required for resilvering, which is the process
  of rebuilding the vdev. The larger the size of the vdev, the longer the resilvering time. When replacing a disk in a RAIDZ*, it is possible that another
  disk will fail before the resilvering process completes. If the number of failed disks exceeds the number allowed per vdev for the type of RAIDZ, the data
  in the pool will be lost. For this reason, RAIDZ1 is not recommended for drives over 1 TB in size.
  
* It is recommended to use drives of equal sizes. While ZFS can create a pool using disks of differing sizes, the capacity will be limited by the size of the
  smallest disk.
