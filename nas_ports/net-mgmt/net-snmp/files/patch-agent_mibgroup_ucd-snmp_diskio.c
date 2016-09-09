--- agent/mibgroup/ucd-snmp/diskio.c.orig	2014-12-08 20:23:22 UTC
+++ agent/mibgroup/ucd-snmp/diskio.c
@@ -944,14 +944,14 @@ var_diskio(struct variable * vp,
         return (u_char *) stat->dinfo->devices[indx].device_name;
     case DISKIO_NREAD:
 #if HAVE_DEVSTAT_GETDEVS
-        long_ret = (signed long) stat->dinfo->devices[indx].bytes[DEVSTAT_READ];
+        long_ret = (signed long) stat->dinfo->devices[indx].bytes[DEVSTAT_READ] & 0xFFFFFFFF;
 #else
         long_ret = (signed long) stat->dinfo->devices[indx].bytes_read;
 #endif
         return (u_char *) & long_ret;
     case DISKIO_NWRITTEN:
 #if HAVE_DEVSTAT_GETDEVS
-        long_ret = (signed long) stat->dinfo->devices[indx].bytes[DEVSTAT_WRITE];
+        long_ret = (signed long) stat->dinfo->devices[indx].bytes[DEVSTAT_WRITE] & 0xFFFFFFFF;
 #else
         long_ret = (signed long) stat->dinfo->devices[indx].bytes_written;
 #endif
@@ -959,7 +959,7 @@ var_diskio(struct variable * vp,
     case DISKIO_NREADX:
         *var_len = sizeof(struct counter64);
 #if HAVE_DEVSTAT_GETDEVS
-        longlong_ret = stat->dinfo->devices[indx].bytes[DEVSTAT_READ];
+        longlong_ret = stat->dinfo->devices[indx].bytes[DEVSTAT_READ] & 0xFFFFFFFF;
 #else
         longlong_ret = stat->dinfo->devices[indx].bytes_read;
 #endif
@@ -969,7 +969,7 @@ var_diskio(struct variable * vp,
     case DISKIO_NWRITTENX:
         *var_len = sizeof(struct counter64);
 #if HAVE_DEVSTAT_GETDEVS
-        longlong_ret = stat->dinfo->devices[indx].bytes[DEVSTAT_WRITE];
+        longlong_ret = stat->dinfo->devices[indx].bytes[DEVSTAT_WRITE] & 0xFFFFFFFF;
 #else
         longlong_ret = stat->dinfo->devices[indx].bytes_written;
 #endif
@@ -978,14 +978,14 @@ var_diskio(struct variable * vp,
         return (u_char *) & c64_ret;
     case DISKIO_READS:
 #if HAVE_DEVSTAT_GETDEVS
-        long_ret = (signed long) stat->dinfo->devices[indx].operations[DEVSTAT_READ];
+        long_ret = (signed long) stat->dinfo->devices[indx].operations[DEVSTAT_READ] & 0xFFFFFFFF;
 #else
         long_ret = (signed long) stat->dinfo->devices[indx].num_reads;
 #endif
         return (u_char *) & long_ret;
     case DISKIO_WRITES:
 #if HAVE_DEVSTAT_GETDEVS
-        long_ret = (signed long) stat->dinfo->devices[indx].operations[DEVSTAT_WRITE];
+        long_ret = (signed long) stat->dinfo->devices[indx].operations[DEVSTAT_WRITE] & 0xFFFFFFFF;
 #else
         long_ret = (signed long) stat->dinfo->devices[indx].num_writes;
 #endif
