--- freebsd_nvme_ioctl.h.orig	2016-03-28 16:25:56 UTC
+++ freebsd_nvme_ioctl.h
@@ -31,6 +31,7 @@
 
 #define	NVME_PASSTHROUGH_CMD	_IOWR('n', 0, struct nvme_pt_command)
 
+#if __FreeBSD_version < 1100110
 struct nvme_command
 {
 	/* dword 0 */
@@ -143,6 +144,9 @@ struct nvme_pt_command {
 	 */
 	struct mtx *		driver_lock;
 };
+#else
+#include <dev/nvme/nvme.h>
+#endif
 
 #define nvme_completion_is_error(cpl)					\
 	((cpl)->status.sc != 0 || (cpl)->status.sct != 0)
