--- modules/freebsd/vmhgfs/vnopscommon.c.orig	2010-10-20 05:19:54.000000000 +0900
+++ modules/freebsd/vmhgfs/vnopscommon.c	2010-11-16 13:26:55.000000000 +0900
@@ -50,7 +50,7 @@
 static int HgfsDoGetattrInt(const char *path, const HgfsHandle handle, HgfsSuperInfo *sip,
 			    HgfsAttrV2 *hgfsAttrV2);
 static int HgfsDoGetattrByName(const char *path, HgfsSuperInfo *sip, HgfsAttrV2 *hgfsAttrV2);
-int HgfsReadlinkInt(struct vnode *vp, struct uio *uiop);
+/* int HgfsReadlinkInt(struct vnode *vp, struct uio *uiop); -> vnopscommon.h */
 static int HgfsQueryAttrInt(const char *path, HgfsHandle handle, HgfsSuperInfo *sip,
                             HgfsKReqHandle req);
 static int HgfsRefreshHandle(struct vnode *vp, HgfsSuperInfo *sip, HgfsHandle *handle);
