--- modules/freebsd/vmblock/vnops.c.orig	2011-09-21 14:25:15.000000000 -0400
+++ modules/freebsd/vmblock/vnops.c	2012-06-28 20:51:22.897344202 -0400
@@ -1362,7 +1362,9 @@
 */
 {
    struct vnode *vp = ap->a_vp;
+#if __FreeBSD_version < 1000000
    struct thread *td = ap->a_td;
+#endif
 
    vp->v_object = NULL;
 
@@ -1370,7 +1372,11 @@
     * If this is the last reference, then free up the vnode so as not to
     * tie up the lower vnode.
     */
+#if __FreeBSD_version < 1000000
    vrecycle(vp, td);
+#else
+   vrecycle(vp);
+#endif
 
    return 0;
 }
