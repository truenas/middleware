--- modules/freebsd/vmhgfs/vfsops.c.orig
+++ modules/freebsd/vmhgfs/vfsops.c
@@ -201,7 +201,9 @@
     * structures, not oplocks/leases with the VM's host.)
     */
+#if __FreeBSD_version < 1000021
    MNT_ILOCK(mp);
    mp->mnt_kern_flag |= MNTK_MPSAFE;
    MNT_IUNLOCK(mp);
+#endif
 
    /* Get a new unique filesystem ID */
