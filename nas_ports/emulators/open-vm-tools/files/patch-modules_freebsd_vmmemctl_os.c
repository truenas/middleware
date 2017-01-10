--- modules/freebsd/vmmemctl/os.c.orig	2013-09-23 15:51:10 UTC
+++ modules/freebsd/vmmemctl/os.c
@@ -824,7 +888,7 @@ vmmemctl_sysctl(SYSCTL_HANDLER_ARGS)
 static void
 vmmemctl_init_sysctl(void)
 {
-   oid =  sysctl_add_oid(NULL, SYSCTL_STATIC_CHILDREN(_vm), OID_AUTO,
+   oid =  SYSCTL_ADD_OID(NULL, SYSCTL_STATIC_CHILDREN(_vm), OID_AUTO,
                          BALLOON_NAME, CTLTYPE_STRING | CTLFLAG_RD,
                          0, 0, vmmemctl_sysctl, "A",
                          BALLOON_NAME_VERBOSE);
