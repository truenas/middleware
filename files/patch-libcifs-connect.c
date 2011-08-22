--- redistributable_sources/libcifs/connect.c.orig	2008-02-02 21:30:04.000000000 -0800
+++ redistributable_sources/libcifs/connect.c	2011-08-20 15:50:55.000000000 -0700
@@ -19,6 +19,9 @@
  *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA 
  */
 
+#if defined(FreeBSD)
+#include <sys/param.h>
+#endif
 #ifndef CIFS_VFS_USERSPACE
 #include <linux/fs.h>
 #include <linux/net.h>
@@ -102,9 +105,10 @@
 	unsigned short int port;
 };
 
-#if defined(FreeBSD) || defined(SOLARIS2) || defined(macosx) 
-int
-strnlen(char *a,int len)
+#if (defined(FreeBSD) && __FreeBSD_version < 800067) || \
+     defined(SOLARIS2) || defined(macosx)
+size_t
+strnlen(const char *a, size_t maxlen)
 {
 	int i,j;
 	j=0;
