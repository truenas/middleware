--- src/geom_stat.c.orig	2016-05-22 07:49:15 UTC
+++ src/geom_stat.c
@@ -0,0 +1,334 @@
+/**
+ * collectd - src/geom.c 
+ * 
+ * Copyright (c) 2003 Poul-Henning Kamp
+ * Copyright (c) 2015 David P. Discher <dpd@ixsystems.com> 
+ * All rights reserved.
+ *
+ * Redistribution and use in source and binary forms, with or without
+ * modification, are permitted provided that the following conditions
+ * are met:
+ * 1. Redistributions of source code must retain the above copyright
+ *    notice, this list of conditions and the following disclaimer.
+ * 2. Redistributions in binary form must reproduce the above copyright
+ *    notice, this list of conditions and the following disclaimer in the
+ *    documentation and/or other materials provided with the distribution.
+ * 3. The names of the authors may not be used to endorse or promote
+ *    products derived from this software without specific prior written
+ *    permission.
+ *
+ * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
+ * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
+ * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
+ * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
+ * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
+ * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
+ * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
+ * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
+ * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
+ * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
+ * SUCH DAMAGE.
+ *
+ * $FreeBSD: stable/10/usr.sbin/gstat/gstat.c 268791 2014-07-17 06:36:22Z delphij $
+ */
+
+
+#include "collectd.h"
+#include "common.h"
+#include "plugin.h"
+
+
+#include <sys/devicestat.h>
+#include <sys/mman.h>
+#include <sys/resource.h>
+#include <sys/time.h>
+
+#include <devstat.h>
+#include <err.h>
+#include <errno.h>
+#include <fcntl.h>
+#include <libgeom.h>
+#include <paths.h>
+#include <regex.h>
+#include <stdint.h>
+#include <stdio.h>
+#include <stdlib.h>
+#include <string.h>
+#include <sysexits.h>
+#include <unistd.h>
+
+
+/*
+ * Global variables
+ */
+
+#include <sys/types.h>
+#include <sys/sysctl.h>
+
+static regex_t f_re;
+static char f_s[100];
+static int fliterSet = 0;
+static int initDone = 0;
+
+static	struct devstat *gsp, *gsq;
+static	void *sp, *sq;
+static	double dt;
+static	struct timespec tp, tq;
+static	struct gmesh gmp;
+
+
+
+static const char *config_keys[] =
+{
+	"Filter"
+};
+static int config_keys_num = STATIC_ARRAY_SIZE (config_keys);
+
+static int geom_init (void) /* {{{ */
+{
+	int error, i;
+	DEBUG("geom_stat: geom_init");
+	if ( !initDone ){
+		DEBUG("geom_stat: geom_init - running init.");
+		fliterSet = 0;
+		i = geom_gettree(&gmp);
+		if (i != 0)
+			err(1, "geom_gettree = %d", i);
+		error = geom_stats_open();
+		if (error)
+			err(1, "geom_stats_open()");
+		sq = NULL;
+		sq = geom_stats_snapshot_get();
+		if (sq == NULL)
+			err(1, "geom_stats_snapshot()");
+		geom_stats_snapshot_timestamp(sq, &tq);
+	}
+	
+	if ( fliterSet == 0 ) {
+		if ( regcomp(&f_re, "^[a]?da[0123456789]+$", REG_EXTENDED) == 0 ) {
+			fliterSet = 1;
+		}
+	}
+	initDone = 1;
+	DEBUG("geom_stat: geom_init - complete.");
+	return (0);
+} /* }}} int geom_init */
+
+
+static int geom_stat_config (const char *key, const char *value)
+{	
+	geom_init();
+	
+	if (0 == strcasecmp (key, "Filter")) {
+
+		if (strlen(value) > sizeof(f_s) - 1) {
+			DEBUG("geom_stat: Filter string too long");
+			return -1;
+		} 
+		if (regcomp(&f_re, value, REG_EXTENDED) != 0) {
+			DEBUG( "geom_stat: Invalid filter - see re_format(7)");
+			return -1;
+		} else {
+			fliterSet = 1;
+			DEBUG( "geom_stat: Valid filter accepted re_format(7) : %s", value);
+		}
+	
+	} else {
+		return -1;
+	}
+	return 0;
+} 
+
+static void geom_submit_trip (const char* type, const char* type_instance, gauge_t read, gauge_t write, gauge_t delete)
+{
+	value_t values[3];
+	value_list_t vl = VALUE_LIST_INIT;
+
+	values[0].gauge = read;
+	values[1].gauge = write;
+	values[2].gauge = delete;
+
+	vl.values = values;
+	vl.values_len = STATIC_ARRAY_SIZE (values);
+	sstrncpy (vl.host, hostname_g, sizeof (vl.host));
+	sstrncpy (vl.plugin, "geom_stat", sizeof (vl.plugin));
+	sstrncpy (vl.type, type, sizeof (vl.type));
+	sstrncpy (vl.type_instance, type_instance, sizeof (vl.type_instance));
+
+	plugin_dispatch_values (&vl);
+}
+
+
+static void geom_submit (const char* type, const char* type_instance, value_t* values, int values_len)
+{
+	value_list_t vl = VALUE_LIST_INIT;
+
+	vl.values = values;
+	vl.values_len = values_len;
+
+	sstrncpy (vl.host, hostname_g, sizeof (vl.host));
+	sstrncpy (vl.plugin, "geom_stat", sizeof (vl.plugin));
+	sstrncpy (vl.type, type, sizeof (vl.type));
+	sstrncpy (vl.type_instance, type_instance, sizeof (vl.type_instance));
+
+	plugin_dispatch_values (&vl);
+}
+
+static void geom_submit_gauge (const char* type, const char* type_instance, gauge_t value)
+{
+	value_t vv;
+
+	vv.gauge = value;
+	geom_submit (type, type_instance, &vv, 1);
+}
+
+
+/* 
+	This read code is largely lifted from FreeBSD's usr.sbin/gstat/gstat.c 
+*/
+static int geom_read (void)
+{
+
+	struct gprovider *pp;
+	struct gconsumer *cp;
+	struct gident *gid;
+	long double ld[11];
+	uint64_t u64;
+	int i, retval;
+
+	sp = geom_stats_snapshot_get();
+	if (sp == NULL)
+		err(1, "geom_stats_snapshot()");
+	geom_stats_snapshot_timestamp(sp, &tp);
+	dt = tp.tv_sec - tq.tv_sec;
+	dt += (tp.tv_nsec - tq.tv_nsec) * 1e-9;
+	tq = tp;
+
+	geom_stats_snapshot_reset(sp);
+	geom_stats_snapshot_reset(sq);
+
+	for (;;) {
+		gsp = geom_stats_snapshot_next(sp);
+		gsq = geom_stats_snapshot_next(sq);
+		if (gsp == NULL || gsq == NULL)
+			break;
+		if (gsp->id == NULL)
+			continue;
+		gid = geom_lookupid(&gmp, gsp->id);
+		if (gid == NULL) {
+			geom_deletetree(&gmp);
+			i = geom_gettree(&gmp);
+			if (i != 0)
+				err(1, "geom_gettree = %d", i);
+			gid = geom_lookupid(&gmp, gsp->id);
+		}
+		if (gid == NULL)
+			continue;
+		if (gid->lg_what == ISCONSUMER )
+			continue;
+		if (  (gid->lg_what == ISPROVIDER || gid->lg_what == ISCONSUMER) && fliterSet ) {
+			pp = gid->lg_ptr;
+			retval = regexec(&f_re, pp->lg_name, 0, NULL, 0);
+			DEBUG("geom_stat: REGEXEC (%d), string: {%s}", retval, pp->lg_name );
+			if ( retval != 0 ) { continue; }
+		} else {		
+			pp = gid->lg_ptr;
+			DEBUG("geom_stat: REGEXEC : Failed to run filter. name: {%s}, what: {%d}, isprovider: {%d}, isconsumer: {%d}, cmp: {%d}", 
+				pp->lg_name,
+				gid->lg_what,
+				ISPROVIDER,
+				ISCONSUMER,
+				fliterSet
+			);			
+		}
+		if (gsp->sequence0 != gsp->sequence1) {
+			continue;
+		}
+		devstat_compute_statistics(gsp, gsq, dt, 
+			DSM_QUEUE_LENGTH, &u64,
+			DSM_TRANSFERS_PER_SECOND, &ld[0],
+
+			DSM_TRANSFERS_PER_SECOND_READ, &ld[1],
+			DSM_MB_PER_SECOND_READ, &ld[2],
+			DSM_MS_PER_TRANSACTION_READ, &ld[3],
+
+			DSM_TRANSFERS_PER_SECOND_WRITE, &ld[4],
+			DSM_MB_PER_SECOND_WRITE, &ld[5],
+			DSM_MS_PER_TRANSACTION_WRITE, &ld[6],
+
+			DSM_BUSY_PCT, &ld[7],
+			DSM_TRANSFERS_PER_SECOND_FREE, &ld[8],
+			DSM_MB_PER_SECOND_FREE, &ld[9],
+			DSM_MS_PER_TRANSACTION_FREE, &ld[10],
+			DSM_NONE);
+
+
+		char geom_name[256];
+				
+		if (gid == NULL) {
+	        snprintf(geom_name, sizeof(geom_name), "%s", "unknown" );			
+		} else if (gid->lg_what == ISPROVIDER) {
+			pp = gid->lg_ptr;
+	        snprintf(geom_name, sizeof(geom_name), "%s", pp->lg_name );
+		} else if (gid->lg_what == ISCONSUMER) {
+			cp = gid->lg_ptr;
+
+	        snprintf(geom_name, sizeof(geom_name), "%s.%s.%s",
+				cp->lg_geom->lg_class->lg_name,
+				cp->lg_geom->lg_name,
+				cp->lg_provider->lg_name);
+		} else {
+	        snprintf(geom_name, sizeof(geom_name), "%s", "undefined" );
+		}
+
+
+		// Queue Length L(q)		
+		geom_submit_gauge( "geom_queue", geom_name, u64);
+
+		// ops/sec
+		geom_submit_gauge( "geom_ops", geom_name, ld[0]);
+		
+		
+		// reads/sec
+		// writes/sec
+		// deletes/sec
+		geom_submit_trip ( "geom_ops_rwd", geom_name , (double)ld[1], (double)ld[4], (double)ld[8] );
+		
+		// kB/s - kBps read
+		// kB/s - KBps write 
+		// kBps delete
+		// Graphic units end up being bytes/second - value is read in MB/sec. 
+		geom_submit_trip ( "geom_bw", geom_name , 
+			(double)ld[2] * 1024 * 1024, 
+			(double)ld[5] * 1024 * 1024, 
+			(double)ld[9] * 1024 * 1024 );
+
+
+		// ms/r			
+		// bio-deletes 		
+		// ms/delete
+		// Units - read and stores as milliseconds
+		geom_submit_trip ( "geom_latency", geom_name , (double)ld[1], (double)ld[4], (double)ld[8] );
+
+		// Busy Percent 
+		geom_submit_gauge( "geom_busy_percent", geom_name, ld[7]);
+
+		*gsq = *gsp;
+	}
+	geom_stats_snapshot_free(sp);
+
+	return (0);
+} /* int geom_read */
+
+
+void module_register (void)
+{
+
+	plugin_register_config ("geom_stat", geom_stat_config,
+			config_keys, config_keys_num);
+
+	plugin_register_init ("geom_stat", geom_init);
+	plugin_register_read ("geom_stat", geom_read);
+} /* void module_register */
+
+/* vmi: set sw=8 noexpandtab fdm=marker : */
