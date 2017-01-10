--- modules/freebsd/vmblock/vfsops.c.orig
+++ modules/freebsd/vmblock/vfsops.c
@@ -236,7 +236,7 @@
     */
    MNT_ILOCK(mp);
    mp->mnt_flag |= lowerrootvp->v_mount->mnt_flag & MNT_LOCAL;
-#if __FreeBSD_version >= 600000
+#if __FreeBSD_version >= 600000 && __FreeBSD_version < 1000021
    mp->mnt_kern_flag |= lowerrootvp->v_mount->mnt_kern_flag & MNTK_MPSAFE;
 #endif
    MNT_IUNLOCK(mp);
