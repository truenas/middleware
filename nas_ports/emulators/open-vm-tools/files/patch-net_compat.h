--- modules/freebsd/vmxnet/net_compat.h.orig	2011-09-21 14:25:15.000000000 -0400
+++ modules/freebsd/vmxnet/net_compat.h	2012-06-28 17:05:44.638526644 -0400
@@ -170,9 +170,12 @@
 #if __FreeBSD_version < 505000
 #   define VXN_IF_ADDR_LOCK(_ifp)
 #   define VXN_IF_ADDR_UNLOCK(_ifp)
+#elif __FreeBSD_version < 1000000
+#  define VXN_IF_ADDR_LOCK(_ifp)           IF_ADDR_LOCK((_ifp))
+#  define VXN_IF_ADDR_UNLOCK(_ifp)         IF_ADDR_UNLOCK((_ifp))
 #else
-#   define VXN_IF_ADDR_LOCK(_ifp)       IF_ADDR_LOCK((_ifp))
-#   define VXN_IF_ADDR_UNLOCK(_ifp)     IF_ADDR_UNLOCK((_ifp))
+#  define VXN_IF_ADDR_LOCK(_ifp)           IF_ADDR_WLOCK((_ifp))
+#  define VXN_IF_ADDR_UNLOCK(_ifp)         IF_ADDR_WUNLOCK((_ifp))
 #endif
 
 #endif /* _VXN_NET_COMPAT_H_ */
