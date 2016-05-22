--- src/zfs_arc_v2.c.orig	2016-05-22 07:00:21 UTC
+++ src/zfs_arc_v2.c
@@ -0,0 +1,447 @@
+/**
+ * collectd - src/zfs_arc_v2.c - forked from the orignal zfs_arc.c 
+ *
+ * Copyright (C) 2009  Anthony Dewhurst
+ * Copyright (C) 2012  Aurelien Rougemont
+ * Copyright (C) 2013  Xin Li
+ * Copyright (C) 2015  David P. Discher
+ *
+ * This program is free software; you can redistribute it and/or modify it
+ * under the terms of the GNU General Public License as published by the
+ * Free Software Foundation; only version 2 of the License is applicable.
+ *
+ * This program is distributed in the hope that it will be useful, but
+ * WITHOUT ANY WARRANTY; without even the implied warranty of
+ * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
+ * General Public License for more details.
+ *
+ * You should have received a copy of the GNU General Public License along
+ * with this program; if not, write to the Free Software Foundation, Inc.,
+ * 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
+ *
+ * Authors:
+ *   Anthony Dewhurst <dewhurst at gmail>
+ *   Aurelien Rougemont <beorn at gandi.net>
+ *   Xin Li <delphij at FreeBSD.org>
+ *   David P. Discher <dpd at ixsystems.com>
+ 
+**/
+
+
+#include "collectd.h"
+#include "common.h"
+#include "plugin.h"
+
+/*
+ * Global variables
+ */
+
+#if !defined(__FreeBSD__)
+extern kstat_ctl_t *kc;
+
+static long long get_zfs_value(kstat_t *ksp, char *name)
+{
+
+	return (get_kstat_value(ksp, name));
+}
+#else
+#include <sys/types.h>
+#include <sys/sysctl.h>
+
+const char zfs_arcstat[] = "kstat.zfs.misc.arcstats.";
+
+#if !defined(kstat_t)
+typedef void kstat_t;
+#endif
+
+typedef struct {
+
+	uint64_t hits;
+	uint64_t misses;
+	uint64_t total;
+	double ratio;	
+
+} zfs_cacheratio;
+
+
+static zfs_cacheratio ratio_arc = { 0, 0, 0, 0 };
+
+static zfs_cacheratio ratio_l2 = { 0, 0, 0, 0 };
+
+static zfs_cacheratio ratio_mru = { 0, 0, 0, 0 };
+static zfs_cacheratio ratio_mfu = { 0, 0, 0, 0 };
+
+//static zfs_cacheratio ratio_mru_ghost = { 0, 0, 0, 0 };
+//static zfs_cacheratio ratio_mfu_ghost = { 0, 0, 0, 0 };
+
+
+static zfs_cacheratio ratio_demand_data = { 0, 0, 0, 0 };
+static zfs_cacheratio ratio_demand_metadata = { 0, 0, 0, 0 };
+
+static zfs_cacheratio ratio_prefetch_data = { 0, 0, 0, 0 };
+static zfs_cacheratio ratio_prefetch_metadata = { 0, 0, 0, 0 };
+
+
+typedef struct  {
+	char *key;
+	char *type;
+	char *type_instance;
+	int  raw;
+	uint64_t previous;
+	uint64_t current;
+	int64_t delta;
+
+} arcstat_item;
+
+static const int arcstat_length = 79;
+static arcstat_item arcstats[79] = {
+{ "hits", "gauge_arcstats_raw_hits_misses", "hits", 0, 0, 0, 0},
+{ "misses", "gauge_arcstats_raw_hits_misses", "misses", 0, 0, 0, 0},
+{ "demand_data_hits", "gauge_arcstats_raw_demand", "demand_data_hits", 0, 0, 0, 0},
+{ "demand_data_misses", "gauge_arcstats_raw_demand", "demand_data_misses", 0, 0, 0, 0},
+{ "demand_metadata_hits", "gauge_arcstats_raw_demand", "demand_metadata_hits", 0, 0, 0, 0},
+{ "demand_metadata_misses", "gauge_arcstats_raw_demand", "demand_metadata_misses", 0, 0, 0, 0},
+{ "prefetch_data_hits", "gauge_arcstats_raw_prefetch", "prefetch_data_hits", 0, 0, 0, 0},
+{ "prefetch_data_misses", "gauge_arcstats_raw_prefetch", "prefetch_data_misses", 0, 0, 0, 0},
+{ "prefetch_metadata_hits", "gauge_arcstats_raw_prefetch", "prefetch_metadata_hits", 0, 0, 0, 0},
+{ "prefetch_metadata_misses", "gauge_arcstats_raw_prefetch", "prefetch_metadata_misses", 0, 0, 0, 0},
+{ "mru_hits", "gauge_arcstats_raw_mru", "mru_hits", 0, 0, 0, 0},
+{ "mru_ghost_hits", "gauge_arcstats_raw_mru", "mru_ghost_hits", 0, 0, 0, 0},
+{ "mfu_hits", "gauge_arcstats_raw_mru", "mfu_hits", 0, 0, 0, 0},
+{ "mfu_ghost_hits", "gauge_arcstats_raw_mru", "mfu_ghost_hits", 0, 0, 0, 0},
+{ "allocated", "gauge_arcstats_raw_counts", "allocated", 0, 0, 0, 0},
+{ "deleted", "gauge_arcstats_raw_counts", "deleted", 0, 0, 0, 0},
+{ "stolen", "gauge_arcstats_raw_counts", "stolen", 0, 0, 0, 0},
+{ "recycle_miss", "gauge_arcstats_raw_counts", "recycle_miss", 0, 0, 0, 0},
+{ "mutex_miss", "gauge_arcstats_raw_counts", "mutex_miss", 0, 0, 0, 0},
+{ "evict_skip", "gauge_arcstats_raw_evict", "evict_skip", 0, 0, 0, 0},
+{ "evict_l2_cached", "gauge_arcstats_raw_evict", "evict_l2_cached", 0, 0, 0, 0},
+{ "evict_l2_eligible", "gauge_arcstats_raw_evict", "evict_l2_eligible", 0, 0, 0, 0},
+{ "evict_l2_ineligible", "gauge_arcstats_raw_evict", "evict_l2_ineligible", 0, 0, 0, 0},
+{ "hash_elements", "gauge_arcstats_raw_hash", "hash_elements", 0, 0, 0, 0},
+{ "hash_elements_max", "gauge_arcstats_raw_hash", "hash_elements_max", 1, 0, 0, 0},
+{ "hash_collisions", "gauge_arcstats_raw_hash", "hash_collisions", 0, 0, 0, 0},
+{ "hash_chains", "gauge_arcstats_raw_hash", "hash_chains", 0, 0, 0, 0},
+{ "hash_chain_max", "gauge_arcstats_raw_hash", "hash_chain_max", 1, 0, 0, 0},
+{ "p", "gauge_arcstats_raw_cp", "p", 1, 0, 0, 0},
+{ "c", "gauge_arcstats_raw_cp", "c", 1, 0, 0, 0},
+{ "c_min", "gauge_arcstats_raw_cp", "c_min", 1, 0, 0, 0},
+{ "c_max", "gauge_arcstats_raw_cp", "c_max", 1, 0, 0, 0},
+{ "size", "gauge_arcstats_raw_size", "size", 1, 0, 0, 0},
+{ "hdr_size", "gauge_arcstats_raw_size", "hdr_size", 1, 0, 0, 0},
+{ "data_size", "gauge_arcstats_raw_size", "data_size", 1, 0, 0, 0},
+{ "other_size", "gauge_arcstats_raw_size", "other_size", 1, 0, 0, 0},
+{ "l2_hits", "gauge_arcstats_raw_l2", "l2_hits", 0, 0, 0, 0},
+{ "l2_misses", "gauge_arcstats_raw_l2", "l2_misses", 0, 0, 0, 0},
+{ "l2_feeds", "gauge_arcstats_raw_l2", "l2_feeds", 0, 0, 0, 0},
+{ "l2_rw_clash", "gauge_arcstats_raw_l2", "l2_rw_clash", 0, 0, 0, 0},
+{ "l2_cksum_bad", "gauge_arcstats_raw_l2", "l2_cksum_bad", 0, 0, 0, 0},
+{ "l2_io_error", "gauge_arcstats_raw_l2", "l2_io_error", 0, 0, 0, 0},
+{ "l2_read_bytes", "gauge_arcstats_raw_l2bytes", "l2_read_bytes", 0, 0, 0, 0},
+{ "l2_write_bytes", "gauge_arcstats_raw_l2bytes", "l2_write_bytes", 0, 0, 0, 0},
+{ "l2_writes_sent", "gauge_arcstats_raw_l2writes", "l2_writes_sent", 0, 0, 0, 0},
+{ "l2_writes_done", "gauge_arcstats_raw_l2writes", "l2_writes_done", 0, 0, 0, 0},
+{ "l2_writes_error", "gauge_arcstats_raw_l2writes", "l2_writes_error", 0, 0, 0, 0},
+{ "l2_writes_hdr_miss", "gauge_arcstats_raw_l2writes", "l2_writes_hdr_miss", 0, 0, 0, 0},
+{ "l2_evict_lock_retry", "gauge_arcstats_raw_l2evict", "l2_evict_lock_retry", 0, 0, 0, 0},
+{ "l2_evict_reading", "gauge_arcstats_raw_l2evict", "l2_evict_reading", 0, 0, 0, 0},
+{ "l2_free_on_write", "gauge_arcstats_raw_l2_free", "l2_free_on_write", 0, 0, 0, 0},
+{ "l2_cdata_free_on_write", "gauge_arcstats_raw_l2_free", "l2_cdata_free_on_write", 0, 0, 0, 0},
+{ "l2_abort_lowmem", "gauge_arcstats_raw_l2abort", "l2_abort_lowmem", 0, 0, 0, 0},
+{ "l2_size", "gauge_arcstats_raw", "l2_size", 1, 0, 0, 0},
+{ "l2_asize", "gauge_arcstats_raw", "l2_asize", 1, 0, 0, 0},
+{ "l2_hdr_size", "gauge_arcstats_raw", "l2_hdr_size", 1, 0, 0, 0},
+{ "l2_compress_successes", "gauge_arcstats_raw_l2_compress", "l2_compress_successes", 0, 0, 0, 0},
+{ "l2_compress_zeros", "gauge_arcstats_raw_l2_compress", "l2_compress_zeros", 0, 0, 0, 0},
+{ "l2_compress_failures", "gauge_arcstats_raw_l2_compress", "l2_compress_failures", 0, 0, 0, 0},
+{ "l2_write_trylock_fail", "gauge_arcstats_raw_l2write", "l2_write_trylock_fail", 0, 0, 0, 0},
+{ "l2_write_passed_headroom", "gauge_arcstats_raw_l2write", "l2_write_passed_headroom", 0, 0, 0, 0},
+{ "l2_write_spa_mismatch", "gauge_arcstats_raw_l2write", "l2_write_spa_mismatch", 0, 0, 0, 0},
+{ "l2_write_in_l2", "gauge_arcstats_raw_l2write", "l2_write_in_l2", 0, 0, 0, 0},
+{ "l2_write_io_in_progress", "gauge_arcstats_raw_l2write", "l2_write_io_in_progress", 0, 0, 0, 0},
+{ "l2_write_not_cacheable", "gauge_arcstats_raw_l2write", "l2_write_not_cacheable", 0, 0, 0, 0},
+{ "l2_write_full", "gauge_arcstats_raw_l2write", "l2_write_full", 0, 0, 0, 0},
+{ "l2_write_buffer_iter", "gauge_arcstats_raw_l2write", "l2_write_buffer_iter", 0, 0, 0, 0},
+{ "l2_write_pios", "gauge_arcstats_raw_l2write", "l2_write_pios", 0, 0, 0, 0},
+{ "l2_write_buffer_bytes_scanned", "gauge_arcstats_raw_l2write", "l2_write_buffer_bytes_scanned", 0, 0, 0, 0},
+{ "l2_write_buffer_list_iter", "gauge_arcstats_raw_l2write", "l2_write_buffer_list_iter", 0, 0, 0, 0},
+{ "l2_write_buffer_list_null_iter", "gauge_arcstats_raw_l2write", "l2_write_buffer_list_null_iter", 0, 0, 0, 0},
+{ "memory_throttle_count", "gauge_arcstats_raw_memcount", "memory_throttle_count", 0, 0, 0, 0},
+{ "duplicate_buffers", "gauge_arcstats_raw_duplicate", "duplicate_buffers", 0, 0, 0, 0},
+{ "duplicate_buffers_size", "gauge_arcstats_raw_duplicate", "duplicate_buffers_size", 1, 0, 0, 0},
+{ "duplicate_reads", "gauge_arcstats_raw_duplicate", "duplicate_reads", 0, 0, 0, 0},
+{ "arc_meta_used", "gauge_arcstats_raw_arcmeta", "arc_meta_used", 1, 0, 0, 0},
+{ "arc_meta_limit", "gauge_arcstats_raw_arcmeta", "arc_meta_limit", 1, 0, 0, 0},
+{ "arc_meta_max", "gauge_arcstats_raw_arcmeta", "arc_meta_max", 1, 0, 0, 0},
+{ "arc_meta_min", "gauge_arcstats_raw_arcmeta", "arc_meta_min", 1, 0, 0, 0},
+};
+
+static void za_v2_ratio_calc (zfs_cacheratio *cr, uint64_t denom ){
+	cr->total = cr->hits + cr->misses;
+
+	/*
+		Division by Zero dilemma in Ratios
+		For the purpose of computer stats, and how in the scope of FreeBSD zfs some
+		of these metrics are collected, Divison by zero will be defined as, 100% if the
+		denominator is greater than zero.
+		
+		Otherwise the ratio is zero. 
+			
+	*/
+
+	if ( cr->total == 0 ) {
+		if ( denom > 0 ) {
+			cr->ratio = 100.0;
+		} else {
+			cr->ratio = 0.0;
+		}
+		DEBUG("zfs_arc_v2: za_v2_ratio_calc by-zero %f ", cr->ratio );
+	} else {
+		cr->ratio =  ( (double)denom / (double)cr->total )  * 100;
+		DEBUG("zfs_arc_v2: za_v2_ratio_calc division  %f ", (double)denom/(double)cr->total );
+	}
+	
+	DEBUG("zfs_arc_v2: za_v2_ratio_calc %ju %ju %f", cr->total, denom, cr->ratio );
+	return;
+
+}
+
+static long long get_zfs_value(kstat_t *dummy __attribute__((unused)),
+		char const *name)
+{
+	char buffer[256];
+	long long value;
+	size_t valuelen = sizeof(value);
+	int rv;
+
+	ssnprintf (buffer, sizeof (buffer), "%s%s", zfs_arcstat, name);
+	rv = sysctlbyname (buffer, (void *) &value, &valuelen,
+			/* new value = */ NULL, /* new length = */ (size_t) 0);
+	if (rv == 0)
+		return (value);
+
+	return (-1);
+}
+
+static void za_v2_calc_arcstat ( kstat_t *ksp, arcstat_item *i  ) {
+
+		DEBUG("zfs_arc_v2: za_v2_calc_arcstat - starting %s", i->key );
+		DEBUG("zfs_arc_v2: za_v2_calc_arcstat - starting %ju %ju %jd", (uint64_t)i->previous, (uint64_t)i->current, (int64_t)i->delta );
+		i->previous = i->current;
+		i->current = get_zfs_value(ksp, i->key);
+		i->delta = i->current - i->previous;
+		return;
+		
+}
+
+#endif
+
+static void za_v2_submit (const char* type, const char* type_instance, value_t* values, int values_len)
+{
+	value_list_t vl = VALUE_LIST_INIT;
+
+	vl.values = values;
+	vl.values_len = values_len;
+
+	sstrncpy (vl.host, hostname_g, sizeof (vl.host));
+	sstrncpy (vl.plugin, "zfs_arc_v2", sizeof (vl.plugin));
+	sstrncpy (vl.type, type, sizeof (vl.type));
+	sstrncpy (vl.type_instance, type_instance, sizeof (vl.type_instance));
+
+	plugin_dispatch_values (&vl);
+}
+
+static void za_v2_submit_gauge (const char* type, const char* type_instance, gauge_t value)
+{
+	value_t vv;
+
+	vv.gauge = value;
+	za_v2_submit (type, type_instance, &vv, 1);
+}
+
+
+static int za_v2_read (void)
+{
+
+	kstat_t	 *ksp	= NULL;
+	int i;
+
+	DEBUG ("zfs: za_v2_read");
+
+#if !defined(__FreeBSD__)
+	get_kstat (&ksp, "zfs", 0, "arcstats");
+	if (ksp == NULL)
+	{
+		ERROR ("zfs_arc_v2: plugin: Cannot find zfs:0:arcstats kstat.");
+		return (-1);
+	}
+#endif
+
+
+/**  gauge ** ****************************************************************************************** */
+
+	// za_v2_read_gauge (ksp, "hits",    "gauge_arcstats_raw_hits_misses", "hits");
+	
+	for (i=0; i<arcstat_length; i++) {
+
+		za_v2_calc_arcstat (ksp, &arcstats[i]);
+		if  ( 1 == arcstats[i].raw ) {
+			za_v2_submit_gauge (arcstats[i].type, arcstats[i].type_instance, (gauge_t) arcstats[i].current);
+		} else {
+			za_v2_submit_gauge (arcstats[i].type, arcstats[i].type_instance, (gauge_t) arcstats[i].delta);
+		}
+		
+		if ( strcmp ( "hits", arcstats[i].key ) == 0 ) {
+			ratio_arc.hits = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		} else if ( strcmp ( "misses", arcstats[i].key ) == 0 ) {
+			ratio_arc.misses = arcstats[i].delta;			
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+
+		} else if ( strcmp ( "demand_data_hits", arcstats[i].key ) == 0 ) {
+			ratio_demand_data.hits = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		} else if ( strcmp ( "demand_data_misses", arcstats[i].key ) == 0 ) {		
+			ratio_demand_data.misses = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+
+		} else if ( strcmp ( "demand_metadata_hits", arcstats[i].key ) == 0 ) {		
+			ratio_demand_metadata.hits = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		} else if ( strcmp ( "demand_metadata_misses", arcstats[i].key ) == 0 ) {		
+			ratio_demand_metadata.misses = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+			
+		} else if ( strcmp ( "prefetch_data_hits", arcstats[i].key ) == 0 ) {
+			ratio_prefetch_data.hits = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		} else if ( strcmp ( "prefetch_data_misses", arcstats[i].key ) == 0 ) {		
+			ratio_prefetch_data.misses = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		
+		} else if ( strcmp ( "prefetch_metadata_hits", arcstats[i].key ) == 0 ) {		
+			ratio_prefetch_metadata.hits = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		} else if ( strcmp ( "prefetch_metadata_misses", arcstats[i].key ) == 0 ) {		
+			ratio_prefetch_metadata.misses = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+
+		} else if ( strcmp ( "mru_hits", arcstats[i].key ) == 0 ) {		
+			ratio_mru.hits = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		} else if ( strcmp ( "mru_ghost_hits", arcstats[i].key ) == 0 ) {
+			ratio_mru.misses = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		
+		} else if ( strcmp ( "mfu_hits", arcstats[i].key ) == 0 ) {		
+			ratio_mfu.hits = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		} else if ( strcmp ( "mfu_ghost_hits", arcstats[i].key ) == 0 ) {
+			ratio_mfu.misses = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		
+		} else if ( strcmp ( "l2_hits", arcstats[i].key ) == 0 ) {		
+			ratio_l2.hits = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		} else if ( strcmp ( "l2_misses", arcstats[i].key ) == 0 ) {		
+			ratio_l2.misses = arcstats[i].delta;
+			DEBUG("zfs_arc_v2: ratio - %s %ju ", arcstats[i].key, ratio_arc.hits );
+		}
+		
+	}
+
+	
+	za_v2_ratio_calc ( &ratio_arc, ratio_arc.hits );
+	za_v2_submit_gauge ("arcstat_ratio_arc", "hits", (gauge_t) ratio_arc.ratio );
+
+	za_v2_ratio_calc ( &ratio_arc, ratio_arc.misses );
+	za_v2_submit_gauge ("arcstat_ratio_arc", "misses", (gauge_t) ratio_arc.ratio );
+
+	za_v2_ratio_calc ( &ratio_l2, ratio_l2.hits );
+	za_v2_submit_gauge ("arcstat_ratio_arc", "l2_hits", (gauge_t) ratio_l2.ratio );
+
+	za_v2_ratio_calc ( &ratio_l2, ratio_l2.misses );
+	za_v2_submit_gauge ("arcstat_ratio_arc", "l2_misses", (gauge_t) ratio_l2.ratio );
+
+	za_v2_ratio_calc ( &ratio_mru, ratio_mru.hits );
+	za_v2_submit_gauge ("arcstat_ratio_mu", "mru_hits", (gauge_t) ratio_mru.ratio );
+
+	za_v2_ratio_calc ( &ratio_mru, ratio_mru.misses );
+	za_v2_submit_gauge ("arcstat_ratio_mu", "mru_ghost_hits", (gauge_t) ratio_mru.ratio );
+
+
+	za_v2_ratio_calc ( &ratio_mfu, ratio_mfu.hits );
+	za_v2_submit_gauge ("arcstat_ratio_mu", "mfu_hits", (gauge_t) ratio_mfu.ratio );
+
+	za_v2_ratio_calc ( &ratio_mfu, ratio_mfu.misses );
+	za_v2_submit_gauge ("arcstat_ratio_mu", "mfu_ghost_hits", (gauge_t) ratio_mfu.ratio );
+
+
+	za_v2_ratio_calc ( &ratio_demand_data, ratio_demand_data.hits );
+	za_v2_submit_gauge ("arcstat_ratio_data", "demand_data_hits", (gauge_t) ratio_demand_data.ratio );
+
+	za_v2_ratio_calc ( &ratio_demand_data, ratio_demand_data.misses );
+	za_v2_submit_gauge ("arcstat_ratio_data", "demand_data_misses", (gauge_t) ratio_demand_data.ratio );
+
+	za_v2_ratio_calc ( &ratio_prefetch_data, ratio_prefetch_data.hits );
+	za_v2_submit_gauge ("arcstat_ratio_data", "prefetch_data_hits", (gauge_t) ratio_prefetch_data.ratio );
+
+	za_v2_ratio_calc ( &ratio_prefetch_data, ratio_prefetch_data.misses );
+	za_v2_submit_gauge ("arcstat_ratio_data", "prefetch_data_misses", (gauge_t) ratio_prefetch_data.ratio );
+
+
+	za_v2_ratio_calc ( &ratio_demand_metadata, ratio_demand_metadata.hits );
+	za_v2_submit_gauge ("arcstat_ratio_metadata", "demand_metadata_hits", (gauge_t) ratio_demand_metadata.ratio );
+
+	za_v2_ratio_calc ( &ratio_demand_metadata, ratio_demand_metadata.misses );
+	za_v2_submit_gauge ("arcstat_ratio_metadata", "demand_metadata_misses", (gauge_t) ratio_demand_metadata.ratio );
+
+
+	za_v2_ratio_calc ( &ratio_prefetch_metadata, ratio_prefetch_metadata.hits );
+	za_v2_submit_gauge ("arcstat_ratio_metadata", "prefetch_metadata_hits", (gauge_t) ratio_prefetch_metadata.ratio );
+
+	za_v2_ratio_calc ( &ratio_prefetch_metadata, ratio_prefetch_metadata.misses  );
+	za_v2_submit_gauge ("arcstat_ratio_metadata", "prefetch_metadata_misses", (gauge_t) ratio_prefetch_metadata.ratio );
+
+
+
+	return (0);
+} /* int za_v2_read */
+
+static int za_v2_init (void) /* {{{ */
+{
+	int i;
+	kstat_t	 *ksp	= NULL;
+#if !defined(__FreeBSD__)
+	get_kstat (&ksp, "zfs", 0, "arcstats");
+	if (ksp == NULL)
+	{
+		ERROR ("zfs_arc_v2 plugin: Cannot find zfs:0:arcstats kstat.");
+		return (-1);
+	}
+#endif
+	
+	DEBUG ("zfs_arc_v2: za_v2_init");
+	for (i=0; i<arcstat_length; i++) {
+		za_v2_calc_arcstat (ksp, &arcstats[i]);
+	}
+	
+#if !defined(__FreeBSD__)
+	/* kstats chain already opened by update_kstat (using *kc), verify everything went fine. */
+	if (kc == NULL)
+	{
+		ERROR ("zfs_arc_v2 plugin: kstat chain control structure not available.");
+		return (-1);
+	}
+#endif
+
+	return (0);
+} /* }}} int za_v2_init */
+
+void module_register (void)
+{
+	plugin_register_init ("zfs_arc_v2", za_v2_init);
+	plugin_register_read ("zfs_arc_v2", za_v2_read);
+} /* void module_register */
+
+/* vmi: set sw=8 noexpandtab fdm=marker : */
