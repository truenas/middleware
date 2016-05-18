--- src/disk.c.orig	2016-01-22 09:51:17 UTC
+++ src/disk.c
@@ -53,6 +53,10 @@
 #if HAVE_IOKIT_IOBSD_H
 #  include <IOKit/IOBSD.h>
 #endif
+#if KERNEL_FREEBSD
+#include <devstat.h>
+#include <libgeom.h>
+#endif
 
 #if HAVE_LIMITS_H
 # include <limits.h>
@@ -107,6 +111,9 @@ typedef struct diskstats
 
 static diskstats_t *disklist;
 /* #endif KERNEL_LINUX */
+#elif KERNEL_FREEBSD
+static struct gmesh geom_tree;
+/* #endif KERNEL_FREEBSD */
 
 #elif HAVE_LIBKSTAT
 #define MAX_NUMDISK 1024
@@ -222,6 +229,21 @@ static int disk_init (void)
 	/* do nothing */
 /* #endif KERNEL_LINUX */
 
+#elif KERNEL_FREEBSD
+	int rv;
+
+	rv = geom_gettree(&geom_tree);
+	if (rv != 0) {
+		ERROR ("geom_gettree() failed, returned %d", rv);
+		return (-1);
+	}
+	rv = geom_stats_open();
+	if (rv != 0) {
+		ERROR ("geom_stats_open() failed, returned %d", rv);
+		return (-1);
+	}
+/* #endif KERNEL_FREEBSD */
+
 #elif HAVE_LIBKSTAT
 	kstat_t *ksp_chain;
 
@@ -505,6 +527,114 @@ static int disk_read (void)
 	IOObjectRelease (disk_list);
 /* #endif HAVE_IOKIT_IOKITLIB_H */
 
+#elif KERNEL_FREEBSD
+	int retry, dirty;
+
+	void *snap = NULL;
+	struct devstat *snap_iter;
+
+	struct gident *geom_id;
+
+	const char *disk_name;
+	long double read_time, write_time;
+
+	for (retry = 0, dirty = 1; retry < 5 && dirty == 1; retry++) {
+		if (snap != NULL)
+			geom_stats_snapshot_free(snap);
+
+		/* Get a fresh copy of stats snapshot */
+		snap = geom_stats_snapshot_get();
+		if (snap == NULL) {
+			ERROR("disk plugin: geom_stats_snapshot_get() failed.");
+			return (-1);
+		}
+
+		/* Check if we have dirty read from this snapshot */
+		dirty = 0;
+		geom_stats_snapshot_reset(snap);
+		while ((snap_iter = geom_stats_snapshot_next(snap)) != NULL) {
+			if (snap_iter->id == NULL)
+				continue;
+			geom_id = geom_lookupid(&geom_tree, snap_iter->id);
+
+			/* New device? refresh GEOM tree */
+			if (geom_id == NULL) {
+				geom_deletetree(&geom_tree);
+				if (geom_gettree(&geom_tree) != 0) {
+					ERROR("disk plugin: geom_gettree() failed");
+					geom_stats_snapshot_free(snap);
+					return (-1);
+				}
+				geom_id = geom_lookupid(&geom_tree, snap_iter->id);
+			}
+			/*
+			 * This should be rare: the device come right before we take the
+			 * snapshot and went away right after it.  We will handle this
+			 * case later, so don't mark dirty but silently ignore it.
+			 */
+			if (geom_id == NULL)
+				continue;
+
+			/* Only collect PROVIDER data */
+			if (geom_id->lg_what != ISPROVIDER)
+				continue;
+
+			/* Only collect data when rank is 1 (physical devices) */
+			if (((struct gprovider *)(geom_id->lg_ptr))->lg_geom->lg_rank != 1)
+				continue;
+
+			/* Check if this is a dirty read quit for another try */
+			if (snap_iter->sequence0 != snap_iter->sequence1) {
+				dirty = 1;
+				break;
+			}
+		}
+	}
+
+	/* Reset iterator */
+	geom_stats_snapshot_reset(snap);
+	for (;;) {
+		snap_iter = geom_stats_snapshot_next(snap);
+		if (snap_iter == NULL)
+			break;
+
+		if (snap_iter->id == NULL)
+			continue;
+		geom_id = geom_lookupid(&geom_tree, snap_iter->id);
+		if (geom_id == NULL)
+			continue;
+		if (geom_id->lg_what != ISPROVIDER)
+			continue;
+		if (((struct gprovider *)(geom_id->lg_ptr))->lg_geom->lg_rank != 1)
+			continue;
+		/* Skip dirty reads, if present */
+		if (dirty && (snap_iter->sequence0 != snap_iter->sequence1))
+			continue;
+
+		disk_name = ((struct gprovider *)geom_id->lg_ptr)->lg_name;
+
+		if ((snap_iter->bytes[1] != 0) || (snap_iter->bytes[2] != 0)) {
+			disk_submit(disk_name, "disk_octets",
+					(derive_t)snap_iter->bytes[1],
+					(derive_t)snap_iter->bytes[2]);
+		}
+
+		if ((snap_iter->operations[1] != 0) || (snap_iter->operations[2] != 0)) {
+			disk_submit(disk_name, "disk_ops",
+					(derive_t)snap_iter->operations[1],
+					(derive_t)snap_iter->operations[2]);
+		}
+
+		read_time = devstat_compute_etime(&snap_iter->duration[DEVSTAT_READ], NULL);
+		write_time = devstat_compute_etime(&snap_iter->duration[DEVSTAT_WRITE], NULL);
+		if ((read_time != 0) || (write_time != 0)) {
+			disk_submit (disk_name, "disk_time",
+					(derive_t)(read_time*1000), (derive_t)(write_time*1000));
+		}
+	}
+	geom_stats_snapshot_free(snap);
+/* #endif KERNEL_FREEBSD */
+
 #elif KERNEL_LINUX
 	FILE *fh;
 	char buffer[1024];
