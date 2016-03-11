commit 0eebd2655842fbb634f67afd44fa4fdcf4e6f189
Author: Ruben Kerkhof <ruben@rubenkerkhof.com>
Date:   Sat Jul 4 22:49:49 2015 +0200

    varnish: fix leak on read
    
    Since VSM_Close doesn't free the object we leak a few bytes
    every interval

commit b208ddc7d08978f4cf52364c1935e94a0479ee42
Author: Marc Fournier <marc.fournier@camptocamp.com>
Date:   Wed Nov 4 21:12:36 2015 +0100

    varnish: isolate varnish v2 code
    
    Segregating v2-specific code will allow reworking the v3 and v4 parts,
    while ensuring backwards compatibility with v2.
    
    The downside is that this leads to a large chunk of mostly duplicate
    code. That said, my suggestion would be to drop support for varnish v2
    in collectd 5.6.
    
    NB: this commit breaks v3 and v4 support.

commit d010d9eff882765201359959a583033dae4b373c
Author: Marc Fournier <marc.fournier@camptocamp.com>
Date:   Wed Nov 4 22:57:00 2015 +0100

    varnish: rework v3 and v4 support
    
    By using VSC_Iter() to loop over the list of metrics exposed by varnish,
    we can pick those we're interested *if they are found*.
    
    Not explicitly referring to metrics in the VSC_C_main struct makes the
    plugin more resilient to small differences between minor varnish
    versions.
    
    It also opens the possibility to monitor non-MAIN metrics, such as
    per-backend or per-storage engine stats.
    
    This patch should be compatible with the previous way of doing, from the
    user point of view.
    
    Fix #1302

commit 08bd4dd86e0fcb6828819cdf6bb3ae2115b1b8f4
Author: Marc Fournier <marc.fournier@camptocamp.com>
Date:   Thu Nov 5 10:23:19 2015 +0100

    varnish: remove unused variable
    
    This was used in a DEBUG statement I didn't check in.

--- src/varnish.c.orig	2015-03-10 14:14:45 UTC
+++ src/varnish.c
@@ -135,6 +135,397 @@ static int varnish_submit_derive (const 
 	return (varnish_submit (plugin_instance, category, type, type_instance, value));
 } /* }}} int varnish_submit_derive */
 
+#if HAVE_VARNISH_V3 || HAVE_VARNISH_V4
+static int varnish_monitor (void *priv, const struct VSC_point * const pt) /* {{{ */
+{
+	uint64_t val;
+	const user_config_t *conf;
+	const char *class;
+	const char *name;
+
+	if (pt == NULL)
+		return (0);
+
+	conf = priv;
+
+#if HAVE_VARNISH_V4
+	class = pt->section->fantom->type;
+	name  = pt->desc->name;
+
+	if (strcmp(class, "MAIN") != 0)
+		return (0);
+
+#elif HAVE_VARNISH_V3
+	class = pt->class;
+	name  = pt->name;
+
+	if (strcmp(class, "") != 0)
+		return (0);
+#endif
+
+	val = *(const volatile uint64_t*) pt->ptr;
+
+	if (conf->collect_cache)
+	{
+		if (strcmp(name, "cache_hit") == 0)
+			return varnish_submit_derive (conf->instance, "cache", "cache_result", "hit",     val);
+		else if (strcmp(name, "cache_miss") == 0)
+			return varnish_submit_derive (conf->instance, "cache", "cache_result", "miss",    val);
+		else if (strcmp(name, "cache_hitpass") == 0)
+			return varnish_submit_derive (conf->instance, "cache", "cache_result", "hitpass", val);
+	}
+
+	if (conf->collect_connections)
+	{
+		if (strcmp(name, "client_conn") == 0)
+			return varnish_submit_derive (conf->instance, "connections", "connections", "accepted", val);
+		else if (strcmp(name, "client_drop") == 0)
+			return varnish_submit_derive (conf->instance, "connections", "connections", "dropped" , val);
+		else if (strcmp(name, "client_req") == 0)
+			return varnish_submit_derive (conf->instance, "connections", "connections", "received", val);
+	}
+
+#ifdef HAVE_VARNISH_V3
+	if (conf->collect_dirdns)
+	{
+		if (strcmp(name, "dir_dns_lookups") == 0)
+			return varnish_submit_derive (conf->instance, "dirdns", "cache_operation", "lookups",    val);
+		else if (strcmp(name, "dir_dns_failed") == 0)
+			return varnish_submit_derive (conf->instance, "dirdns", "cache_result",    "failed",     val);
+		else if (strcmp(name, "dir_dns_hit") == 0)
+			return varnish_submit_derive (conf->instance, "dirdns", "cache_result",    "hits",       val);
+		else if (strcmp(name, "dir_dns_cache_full") == 0)
+			return varnish_submit_derive (conf->instance, "dirdns", "cache_result",    "cache_full", val);
+	}
+#endif
+
+	if (conf->collect_esi)
+	{
+		if (strcmp(name, "esi_errors") == 0)
+			return varnish_submit_derive (conf->instance, "esi", "total_operations", "error",   val);
+		else if (strcmp(name, "esi_parse") == 0)
+			return varnish_submit_derive (conf->instance, "esi", "total_operations", "parsed",  val);
+		else if (strcmp(name, "esi_warnings") == 0)
+			return varnish_submit_derive (conf->instance, "esi", "total_operations", "warning", val);
+	}
+
+	if (conf->collect_backend)
+	{
+		if (strcmp(name, "backend_conn") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "connections", "success",       val);
+		else if (strcmp(name, "backend_unhealthy") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "connections", "not-attempted", val);
+		else if (strcmp(name, "backend_busy") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "connections", "too-many",      val);
+		else if (strcmp(name, "backend_fail") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "connections", "failures",      val);
+		else if (strcmp(name, "backend_reuse") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "connections", "reuses",        val);
+		else if (strcmp(name, "backend_toolate") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "connections", "was-closed",    val);
+		else if (strcmp(name, "backend_recycle") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "connections", "recycled",      val);
+		else if (strcmp(name, "backend_unused") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "connections", "unused",        val);
+		else if (strcmp(name, "backend_retry") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "connections", "retries",       val);
+		else if (strcmp(name, "backend_req") == 0)
+			return varnish_submit_derive (conf->instance, "backend", "http_requests", "requests",    val);
+		else if (strcmp(name, "n_backend") == 0)
+			return varnish_submit_gauge  (conf->instance, "backend", "backends", "n_backends",       val);
+	}
+
+	if (conf->collect_fetch)
+	{
+		if (strcmp(name, "fetch_head") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "head",        val);
+		else if (strcmp(name, "fetch_length") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "length",      val);
+		else if (strcmp(name, "fetch_chunked") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "chunked",     val);
+		else if (strcmp(name, "fetch_eof") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "eof",         val);
+		else if (strcmp(name, "fetch_bad") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "bad_headers", val);
+		else if (strcmp(name, "fetch_close") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "close",       val);
+		else if (strcmp(name, "fetch_oldhttp") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "oldhttp",     val);
+		else if (strcmp(name, "fetch_zero") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "zero",        val);
+		else if (strcmp(name, "fetch_failed") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "failed",      val);
+		else if (strcmp(name, "fetch_1xx") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "no_body_1xx", val);
+		else if (strcmp(name, "fetch_204") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "no_body_204", val);
+		else if (strcmp(name, "fetch_304") == 0)
+			return varnish_submit_derive (conf->instance, "fetch", "http_requests", "no_body_304", val);
+	}
+
+	if (conf->collect_hcb)
+	{
+		if (strcmp(name, "hcb_nolock") == 0)
+			return varnish_submit_derive (conf->instance, "hcb", "cache_operation", "lookup_nolock", val);
+		else if (strcmp(name, "hcb_lock") == 0)
+			return varnish_submit_derive (conf->instance, "hcb", "cache_operation", "lookup_lock",   val);
+		else if (strcmp(name, "hcb_insert") == 0)
+			return varnish_submit_derive (conf->instance, "hcb", "cache_operation", "insert",        val);
+	}
+
+	if (conf->collect_objects)
+	{
+		if (strcmp(name, "n_expired") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "expired",            val);
+		else if (strcmp(name, "n_lru_nuked") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "lru_nuked",          val);
+		else if (strcmp(name, "n_lru_saved") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "lru_saved",          val);
+		else if (strcmp(name, "n_lru_moved") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "lru_moved",          val);
+		else if (strcmp(name, "n_deathrow") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "deathrow",           val);
+		else if (strcmp(name, "losthdr") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "header_overflow",    val);
+		else if (strcmp(name, "n_obj_purged") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "purged",             val);
+		else if (strcmp(name, "n_objsendfile") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "sent_sendfile",      val);
+		else if (strcmp(name, "n_objwrite") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "sent_write",         val);
+		else if (strcmp(name, "n_objoverflow") == 0)
+			return varnish_submit_derive (conf->instance, "objects", "total_objects", "workspace_overflow", val);
+	}
+
+#if HAVE_VARNISH_V3
+	if (conf->collect_ban)
+	{
+		if (strcmp(name, "n_ban") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "total",          val);
+		else if (strcmp(name, "n_ban_add") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "added",          val);
+		else if (strcmp(name, "n_ban_retire") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "deleted",        val);
+		else if (strcmp(name, "n_ban_obj_test") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "objects_tested", val);
+		else if (strcmp(name, "n_ban_re_test") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "regexps_tested", val);
+		else if (strcmp(name, "n_ban_dups") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "duplicate",      val);
+	}
+#endif
+#if HAVE_VARNISH_V4
+	if (conf->collect_ban)
+	{
+		if (strcmp(name, "bans") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "total",     val);
+		else if (strcmp(name, "bans_added") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "added",     val);
+		else if (strcmp(name, "bans_obj") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "obj",       val);
+		else if (strcmp(name, "bans_req") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "req",       val);
+		else if (strcmp(name, "bans_completed") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "completed", val);
+		else if (strcmp(name, "bans_deleted") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "deleted",   val);
+		else if (strcmp(name, "bans_tested") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "tested",    val);
+		else if (strcmp(name, "bans_dups") == 0)
+			return varnish_submit_derive (conf->instance, "ban", "total_operations", "duplicate", val);
+	}
+#endif
+
+	if (conf->collect_session)
+	{
+		if (strcmp(name, "sess_closed") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "closed",    val);
+		else if (strcmp(name, "sess_pipeline") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "pipeline",  val);
+		else if (strcmp(name, "sess_readahead") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "readahead", val);
+		else if (strcmp(name, "sess_conn") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "accepted",  val);
+		else if (strcmp(name, "sess_drop") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "dropped",   val);
+		else if (strcmp(name, "sess_fail") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "failed",    val);
+		else if (strcmp(name, "sess_pipe_overflow") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "overflow",  val);
+		else if (strcmp(name, "sess_queued") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "queued",    val);
+		else if (strcmp(name, "sess_linger") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "linger",    val);
+		else if (strcmp(name, "sess_herd") == 0)
+			return varnish_submit_derive (conf->instance, "session", "total_operations", "herd",      val);
+	}
+
+	if (conf->collect_shm)
+	{
+		if (strcmp(name, "shm_records") == 0)
+			return varnish_submit_derive (conf->instance, "shm", "total_operations", "records",    val);
+		else if (strcmp(name, "shm_writes") == 0)
+			return varnish_submit_derive (conf->instance, "shm", "total_operations", "writes",     val);
+		else if (strcmp(name, "shm_flushes") == 0)
+			return varnish_submit_derive (conf->instance, "shm", "total_operations", "flushes",    val);
+		else if (strcmp(name, "shm_cont") == 0)
+			return varnish_submit_derive (conf->instance, "shm", "total_operations", "contention", val);
+		else if (strcmp(name, "shm_cycles") == 0)
+			return varnish_submit_derive (conf->instance, "shm", "total_operations", "cycles",     val);
+	}
+
+	if (conf->collect_sms)
+	{
+		if (strcmp(name, "sms_nreq") == 0)
+			return varnish_submit_derive (conf->instance, "sms", "total_requests", "allocator", val);
+		else if (strcmp(name, "sms_nobj") == 0)
+			return varnish_submit_gauge (conf->instance,  "sms", "requests", "outstanding",     val);
+		else if (strcmp(name, "sms_nbytes") == 0)
+			return varnish_submit_gauge (conf->instance,  "sms", "bytes", "outstanding",        val);
+		else if (strcmp(name, "sms_balloc") == 0)
+			return varnish_submit_derive (conf->instance,  "sms", "total_bytes", "allocated",   val);
+		else if (strcmp(name, "sms_bfree") == 0)
+			return varnish_submit_derive (conf->instance,  "sms", "total_bytes", "free",        val);
+	}
+
+	if (conf->collect_struct)
+	{
+		if (strcmp(name, "n_sess_mem") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "current_sessions", "sess_mem",  val);
+		else if (strcmp(name, "n_sess") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "current_sessions", "sess",      val);
+		else if (strcmp(name, "n_object") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "objects", "object",             val);
+		else if (strcmp(name, "n_vampireobject") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "objects", "vampireobject",      val);
+		else if (strcmp(name, "n_objectcore") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "objects", "objectcore",         val);
+		else if (strcmp(name, "n_waitinglist") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "objects", "waitinglist",        val);
+		else if (strcmp(name, "n_objecthead") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "objects", "objecthead",         val);
+		else if (strcmp(name, "n_smf") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "objects", "smf",                val);
+		else if (strcmp(name, "n_smf_frag") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "objects", "smf_frag",           val);
+		else if (strcmp(name, "n_smf_large") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "objects", "smf_large",          val);
+		else if (strcmp(name, "n_vbe_conn") == 0)
+			return varnish_submit_gauge (conf->instance, "struct", "objects", "vbe_conn",           val);
+	}
+
+	if (conf->collect_totals)
+	{
+		if (strcmp(name, "s_sess") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_sessions", "sessions",  val);
+		else if (strcmp(name, "s_req") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_requests", "requests",  val);
+		else if (strcmp(name, "s_pipe") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_operations", "pipe",    val);
+		else if (strcmp(name, "s_pass") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_operations", "pass",    val);
+		else if (strcmp(name, "s_fetch") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_operations", "fetches", val);
+		else if (strcmp(name, "s_synth") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "synth",        val);
+		else if (strcmp(name, "s_req_hdrbytes") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "req_header",   val);
+		else if (strcmp(name, "s_req_bodybytes") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "req_body",     val);
+		else if (strcmp(name, "s_resp_hdrbytes") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "resp_header",  val);
+		else if (strcmp(name, "s_resp_bodybytes") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "resp_body",    val);
+		else if (strcmp(name, "s_pipe_hdrbytes") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "pipe_header",  val);
+		else if (strcmp(name, "s_pipe_in") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "pipe_in",      val);
+		else if (strcmp(name, "s_pipe_out") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "pipe_out",     val);
+		else if (strcmp(name, "n_purges") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_operations", "purges",  val);
+		else if (strcmp(name, "s_hdrbytes") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "header-bytes", val);
+		else if (strcmp(name, "s_bodybytes") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_bytes", "body-bytes",   val);
+		else if (strcmp(name, "n_gzip") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_operations", "gzip",    val);
+		else if (strcmp(name, "n_gunzip") == 0)
+			return varnish_submit_derive (conf->instance, "totals", "total_operations", "gunzip",  val);
+	}
+
+	if (conf->collect_uptime)
+	{
+		if (strcmp(name, "uptime") == 0)
+			return varnish_submit_gauge (conf->instance, "uptime", "uptime", "client_uptime", val);
+	}
+
+	if (conf->collect_vcl)
+	{
+		if (strcmp(name, "n_vcl") == 0)
+			return varnish_submit_gauge (conf->instance, "vcl", "vcl", "total_vcl",     val);
+		else if (strcmp(name, "n_vcl_avail") == 0)
+			return varnish_submit_gauge (conf->instance, "vcl", "vcl", "avail_vcl",     val);
+		else if (strcmp(name, "n_vcl_discard") == 0)
+			return varnish_submit_gauge (conf->instance, "vcl", "vcl", "discarded_vcl", val);
+		else if (strcmp(name, "vmods") == 0)
+			return varnish_submit_gauge (conf->instance, "vcl", "objects", "vmod",      val);
+	}
+
+	if (conf->collect_workers)
+	{
+		if (strcmp(name, "threads") == 0)
+			return varnish_submit_gauge (conf->instance, "workers", "threads", "worker",               val);
+		else if (strcmp(name, "threads_created") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_threads", "created",       val);
+		else if (strcmp(name, "threads_failed") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_threads", "failed",        val);
+		else if (strcmp(name, "threads_limited") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_threads", "limited",       val);
+		else if (strcmp(name, "threads_destroyed") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_threads", "dropped",       val);
+		else if (strcmp(name, "thread_queue_len") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "queue_length",  "threads",       val);
+		else if (strcmp(name, "n_wrk") == 0)
+			return varnish_submit_gauge (conf->instance, "workers", "threads", "worker",               val);
+		else if (strcmp(name, "n_wrk_create") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_threads", "created",       val);
+		else if (strcmp(name, "n_wrk_failed") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_threads", "failed",        val);
+		else if (strcmp(name, "n_wrk_max") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_threads", "limited",       val);
+		else if (strcmp(name, "n_wrk_drop") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_threads", "dropped",       val);
+		else if (strcmp(name, "n_wrk_queue") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_requests", "queued",       val);
+		else if (strcmp(name, "n_wrk_overflow") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_requests", "overflowed",   val);
+		else if (strcmp(name, "n_wrk_queued") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_requests", "queued",       val);
+		else if (strcmp(name, "n_wrk_lqueue") == 0)
+			return varnish_submit_derive (conf->instance, "workers", "total_requests", "queue_length", val);
+	}
+
+#if HAVE_VARNISH_V4
+	if (conf->collect_vsm)
+	{
+		if (strcmp(name, "vsm_free") == 0)
+			return varnish_submit_gauge (conf->instance, "vsm", "bytes", "free",              val);
+		else if (strcmp(name, "vsm_used") == 0)
+			return varnish_submit_gauge (conf->instance, "vsm", "bytes", "used",              val);
+		else if (strcmp(name, "vsm_cooling") == 0)
+			return varnish_submit_gauge (conf->instance, "vsm", "bytes", "cooling",           val);
+		else if (strcmp(name, "vsm_overflow") == 0)
+			return varnish_submit_gauge (conf->instance, "vsm", "bytes", "overflow",          val);
+		else if (strcmp(name, "vsm_overflowed") == 0)
+			return varnish_submit_derive (conf->instance, "vsm", "total_bytes", "overflowed", val);
+	}
+#endif
+
+	return (0);
+
+} /* }}} static int varnish_monitor */
+#else /* if HAVE_VARNISH_V2 */
 static void varnish_monitor (const user_config_t *conf, /* {{{ */
 		const c_varnish_stats_t *stats)
 {
@@ -150,41 +541,20 @@ static void varnish_monitor (const user_
 
 	if (conf->collect_connections)
 	{
-#ifndef HAVE_VARNISH_V4
 		/* Client connections accepted */
 		varnish_submit_derive (conf->instance, "connections", "connections", "accepted", stats->client_conn);
 		/* Connection dropped, no sess */
 		varnish_submit_derive (conf->instance, "connections", "connections", "dropped" , stats->client_drop);
-#endif
 		/* Client requests received    */
 		varnish_submit_derive (conf->instance, "connections", "connections", "received", stats->client_req);
 	}
 
-#ifdef HAVE_VARNISH_V3
-	if (conf->collect_dirdns)
-	{
-		/* DNS director lookups */
-		varnish_submit_derive (conf->instance, "dirdns", "cache_operation", "lookups",    stats->dir_dns_lookups);
-		/* DNS director failed lookups */
-		varnish_submit_derive (conf->instance, "dirdns", "cache_result",    "failed",     stats->dir_dns_failed);
-		/* DNS director cached lookups hit */
-		varnish_submit_derive (conf->instance, "dirdns", "cache_result",    "hits",       stats->dir_dns_hit);
-		/* DNS director full dnscache */
-		varnish_submit_derive (conf->instance, "dirdns", "cache_result",    "cache_full", stats->dir_dns_cache_full);
-	}
-#endif
-
 	if (conf->collect_esi)
 	{
 		/* ESI parse errors (unlock)   */
 		varnish_submit_derive (conf->instance, "esi", "total_operations", "error",   stats->esi_errors);
-#if HAVE_VARNISH_V2
 		/* Objects ESI parsed (unlock) */
 		varnish_submit_derive (conf->instance, "esi", "total_operations", "parsed",  stats->esi_parse);
-#else
-		/* ESI parse warnings (unlock) */
-		varnish_submit_derive (conf->instance, "esi", "total_operations", "warning", stats->esi_warnings);
-#endif
 	}
 
 	if (conf->collect_backend)
@@ -203,13 +573,8 @@ static void varnish_monitor (const user_
 		varnish_submit_derive (conf->instance, "backend", "connections", "was-closed"   , stats->backend_toolate);
 		/* Backend conn. recycles      */
 		varnish_submit_derive (conf->instance, "backend", "connections", "recycled"     , stats->backend_recycle);
-#if HAVE_VARNISH_V2
 		/* Backend conn. unused        */
 		varnish_submit_derive (conf->instance, "backend", "connections", "unused"       , stats->backend_unused);
-#else
-		/* Backend conn. retry         */
-		varnish_submit_derive (conf->instance, "backend", "connections", "retries"      , stats->backend_retry);
-#endif
 		/* Backend requests mades      */
 		varnish_submit_derive (conf->instance, "backend", "http_requests", "requests"   , stats->backend_req);
 		/* N backends                  */
@@ -236,14 +601,6 @@ static void varnish_monitor (const user_
 		varnish_submit_derive (conf->instance, "fetch", "http_requests", "zero"       , stats->fetch_zero);
 		/* Fetch failed              */
 		varnish_submit_derive (conf->instance, "fetch", "http_requests", "failed"     , stats->fetch_failed);
-#if HAVE_VARNISH_V3 || HAVE_VARNISH_V4
-		/* Fetch no body (1xx)       */
-		varnish_submit_derive (conf->instance, "fetch", "http_requests", "no_body_1xx", stats->fetch_1xx);
-		/* Fetch no body (204)       */
-		varnish_submit_derive (conf->instance, "fetch", "http_requests", "no_body_204", stats->fetch_204);
-		/* Fetch no body (304)       */
-		varnish_submit_derive (conf->instance, "fetch", "http_requests", "no_body_304", stats->fetch_304);
-#endif
 	}
 
 	if (conf->collect_hcb)
@@ -262,32 +619,22 @@ static void varnish_monitor (const user_
 		varnish_submit_derive (conf->instance, "objects", "total_objects", "expired",            stats->n_expired);
 		/* N LRU nuked objects           */
 		varnish_submit_derive (conf->instance, "objects", "total_objects", "lru_nuked",          stats->n_lru_nuked);
-#if HAVE_VARNISH_V2
 		/* N LRU saved objects           */
 		varnish_submit_derive (conf->instance, "objects", "total_objects", "lru_saved",          stats->n_lru_saved);
-#endif
 		/* N LRU moved objects           */
 		varnish_submit_derive (conf->instance, "objects", "total_objects", "lru_moved",          stats->n_lru_moved);
-#if HAVE_VARNISH_V2
 		/* N objects on deathrow         */
 		varnish_submit_derive (conf->instance, "objects", "total_objects", "deathrow",           stats->n_deathrow);
-#endif
 		/* HTTP header overflows         */
 		varnish_submit_derive (conf->instance, "objects", "total_objects", "header_overflow",    stats->losthdr);
-#if HAVE_VARNISH_V4
-		/* N purged objects              */
-		varnish_submit_derive (conf->instance, "objects", "total_objects", "purged",             stats->n_obj_purged);
-#else
 		/* Objects sent with sendfile    */
 		varnish_submit_derive (conf->instance, "objects", "total_objects", "sent_sendfile",      stats->n_objsendfile);
 		/* Objects sent with write       */
 		varnish_submit_derive (conf->instance, "objects", "total_objects", "sent_write",         stats->n_objwrite);
 		/* Objects overflowing workspace */
 		varnish_submit_derive (conf->instance, "objects", "total_objects", "workspace_overflow", stats->n_objoverflow);
-#endif
 	}
 
-#if HAVE_VARNISH_V2
 	if (conf->collect_purge)
 	{
 		/* N total active purges      */
@@ -303,45 +650,6 @@ static void varnish_monitor (const user_
 		/* N duplicate purges removed */
 		varnish_submit_derive (conf->instance, "purge", "total_operations", "duplicate",        stats->n_purge_dups);
 	}
-#endif
-#if HAVE_VARNISH_V3
-	if (conf->collect_ban)
-	{
-		/* N total active bans      */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "total",          stats->n_ban);
-		/* N new bans added         */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "added",          stats->n_ban_add);
-		/* N old bans deleted       */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "deleted",        stats->n_ban_retire);
-		/* N objects tested         */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "objects_tested", stats->n_ban_obj_test);
-		/* N regexps tested against */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "regexps_tested", stats->n_ban_re_test);
-		/* N duplicate bans removed */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "duplicate",      stats->n_ban_dups);
-	}
-#endif
-#if HAVE_VARNISH_V4
-	if (conf->collect_ban)
-	{
-		/* N total active bans      */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "total",          stats->bans);
-		/* N new bans added         */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "added",          stats->bans_added);
-		/* N bans using obj */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "obj",            stats->bans_obj);
-		/* N bans using req */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "req",            stats->bans_req);
-		/* N new bans completed     */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "completed",      stats->bans_completed);
-		/* N old bans deleted       */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "deleted",        stats->bans_deleted);
-		/* N objects tested         */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "tested",         stats->bans_tested);
-		/* N duplicate bans removed */
-		varnish_submit_derive (conf->instance, "ban", "total_operations", "duplicate",      stats->bans_dups);
-	}
-#endif
 
 	if (conf->collect_session)
 	{
@@ -351,21 +659,8 @@ static void varnish_monitor (const user_
 		varnish_submit_derive (conf->instance, "session", "total_operations", "pipeline",  stats->sess_pipeline);
 		/* Session Read Ahead */
 		varnish_submit_derive (conf->instance, "session", "total_operations", "readahead", stats->sess_readahead);
-#if HAVE_VARNISH_V4
-		/* Sessions accepted */
-		varnish_submit_derive (conf->instance, "session", "total_operations", "accepted",  stats->sess_conn);
-		/* Sessions dropped for thread */
-		varnish_submit_derive (conf->instance, "session", "total_operations", "dropped",   stats->sess_drop);
-		/* Sessions accept failure */
-		varnish_submit_derive (conf->instance, "session", "total_operations", "failed",    stats->sess_fail);
-		/* Sessions pipe overflow */
-		varnish_submit_derive (conf->instance, "session", "total_operations", "overflow",  stats->sess_pipe_overflow);
-		/* Sessions queued for thread */
-		varnish_submit_derive (conf->instance, "session", "total_operations", "queued",    stats->sess_queued);
-#else
 		/* Session Linger     */
 		varnish_submit_derive (conf->instance, "session", "total_operations", "linger",    stats->sess_linger);
-#endif
 		/* Session herd       */
 		varnish_submit_derive (conf->instance, "session", "total_operations", "herd",      stats->sess_herd);
 	}
@@ -384,7 +679,6 @@ static void varnish_monitor (const user_
 		varnish_submit_derive (conf->instance, "shm", "total_operations", "cycles"    , stats->shm_cycles);
 	}
 
-#if HAVE_VARNISH_V2
 	if (conf->collect_sm)
 	{
 		/* allocator requests */
@@ -410,7 +704,6 @@ static void varnish_monitor (const user_
 		/* SMA bytes free */
 		varnish_submit_derive (conf->instance,  "sma", "total_bytes", "free" ,     stats->sma_bfree);
 	}
-#endif
 
 	if (conf->collect_sms)
 	{
@@ -428,25 +721,14 @@ static void varnish_monitor (const user_
 
 	if (conf->collect_struct)
 	{
-#if !HAVE_VARNISH_V4
 		/* N struct sess_mem       */
 		varnish_submit_gauge (conf->instance, "struct", "current_sessions", "sess_mem",  stats->n_sess_mem);
 		/* N struct sess           */
 		varnish_submit_gauge (conf->instance, "struct", "current_sessions", "sess",      stats->n_sess);
-#endif
 		/* N struct object         */
 		varnish_submit_gauge (conf->instance, "struct", "objects", "object",             stats->n_object);
-#if HAVE_VARNISH_V3 || HAVE_VARNISH_V4
-		/* N unresurrected objects */
-		varnish_submit_gauge (conf->instance, "struct", "objects", "vampireobject",      stats->n_vampireobject);
-		/* N struct objectcore     */
-		varnish_submit_gauge (conf->instance, "struct", "objects", "objectcore",         stats->n_objectcore);
-		/* N struct waitinglist    */
-		varnish_submit_gauge (conf->instance, "struct", "objects", "waitinglist",        stats->n_waitinglist);
-#endif
 		/* N struct objecthead     */
 		varnish_submit_gauge (conf->instance, "struct", "objects", "objecthead",         stats->n_objecthead);
-#ifdef HAVE_VARNISH_V2
 		/* N struct smf            */
 		varnish_submit_gauge (conf->instance, "struct", "objects", "smf",                stats->n_smf);
 		/* N small free smf         */
@@ -455,7 +737,6 @@ static void varnish_monitor (const user_
 		varnish_submit_gauge (conf->instance, "struct", "objects", "smf_large",          stats->n_smf_large);
 		/* N struct vbe_conn        */
 		varnish_submit_gauge (conf->instance, "struct", "objects", "vbe_conn",           stats->n_vbe_conn);
-#endif
 	}
 
 	if (conf->collect_totals)
@@ -470,47 +751,12 @@ static void varnish_monitor (const user_
 		varnish_submit_derive (conf->instance, "totals", "total_operations", "pass",    stats->s_pass);
 		/* Total fetch */
 		varnish_submit_derive (conf->instance, "totals", "total_operations", "fetches", stats->s_fetch);
-#if HAVE_VARNISH_V4
-		/* Total synth */
-		varnish_submit_derive (conf->instance, "totals", "total_bytes", "synth",       stats->s_synth);
-		/* Request header bytes */
-		varnish_submit_derive (conf->instance, "totals", "total_bytes", "req_header",  stats->s_req_hdrbytes);
-		/* Request body byte */
-		varnish_submit_derive (conf->instance, "totals", "total_bytes", "req_body",    stats->s_req_bodybytes);
-		/* Response header bytes */
-		varnish_submit_derive (conf->instance, "totals", "total_bytes", "resp_header", stats->s_resp_hdrbytes);
-		/* Response body byte */
-		varnish_submit_derive (conf->instance, "totals", "total_bytes", "resp_body",   stats->s_resp_bodybytes);
-		/* Pipe request header bytes */
-		varnish_submit_derive (conf->instance, "totals", "total_bytes", "pipe_header", stats->s_pipe_hdrbytes);
-		/* Piped bytes from client */
-		varnish_submit_derive (conf->instance, "totals", "total_bytes", "pipe_in",     stats->s_pipe_in);
-		/* Piped bytes to client */
-		varnish_submit_derive (conf->instance, "totals", "total_bytes", "pipe_out",    stats->s_pipe_out);
-		/* Number of purge operations */
-		varnish_submit_derive (conf->instance, "totals", "total_operations", "purges", stats->n_purges);
-#else
 		/* Total header bytes */
 		varnish_submit_derive (conf->instance, "totals", "total_bytes", "header-bytes", stats->s_hdrbytes);
 		/* Total body byte */
 		varnish_submit_derive (conf->instance, "totals", "total_bytes", "body-bytes",   stats->s_bodybytes);
-#endif
-#if HAVE_VARNISH_V3 || HAVE_VARNISH_V4
-		/* Gzip operations */
-		varnish_submit_derive (conf->instance, "totals", "total_operations", "gzip",    stats->n_gzip);
-		/* Gunzip operations */
-		varnish_submit_derive (conf->instance, "totals", "total_operations", "gunzip",  stats->n_gunzip);
-#endif
 	}
 
-#if HAVE_VARNISH_V3 || HAVE_VARNISH_V4
-	if (conf->collect_uptime)
-	{
-		/* Client uptime */
-		varnish_submit_gauge (conf->instance, "uptime", "uptime", "client_uptime", stats->uptime);
-	}
-#endif
-
 	if (conf->collect_vcl)
 	{
 		/* N vcl total     */
@@ -519,28 +765,10 @@ static void varnish_monitor (const user_
 		varnish_submit_gauge (conf->instance, "vcl", "vcl", "avail_vcl",     stats->n_vcl_avail);
 		/* N vcl discarded */
 		varnish_submit_gauge (conf->instance, "vcl", "vcl", "discarded_vcl", stats->n_vcl_discard);
-#if HAVE_VARNISH_V3 || HAVE_VARNISH_V4
-		/* Loaded VMODs */
-		varnish_submit_gauge (conf->instance, "vcl", "objects", "vmod",      stats->vmods);
-#endif
 	}
 
 	if (conf->collect_workers)
 	{
-#ifdef HAVE_VARNISH_V4
-		/* total number of threads */
-		varnish_submit_gauge (conf->instance, "workers", "threads", "worker",             stats->threads);
-		/* threads created */
-		varnish_submit_derive (conf->instance, "workers", "total_threads", "created",     stats->threads_created);
-		/* thread creation failed */
-		varnish_submit_derive (conf->instance, "workers", "total_threads", "failed",      stats->threads_failed);
-		/* threads hit max */
-		varnish_submit_derive (conf->instance, "workers", "total_threads", "limited",     stats->threads_limited);
-		/* threads destroyed */
-		varnish_submit_derive (conf->instance, "workers", "total_threads", "dropped",     stats->threads_destroyed);
-		/* length of session queue */
-		varnish_submit_derive (conf->instance, "workers", "queue_length",  "threads",     stats->thread_queue_len);
-#else
 		/* worker threads */
 		varnish_submit_gauge (conf->instance, "workers", "threads", "worker",             stats->n_wrk);
 		/* worker threads created */
@@ -551,37 +779,14 @@ static void varnish_monitor (const user_
 		varnish_submit_derive (conf->instance, "workers", "total_threads", "limited",     stats->n_wrk_max);
 		/* dropped work requests */
 		varnish_submit_derive (conf->instance, "workers", "total_threads", "dropped",     stats->n_wrk_drop);
-#ifdef HAVE_VARNISH_V2
 		/* queued work requests */
 		varnish_submit_derive (conf->instance, "workers", "total_requests", "queued",     stats->n_wrk_queue);
 		/* overflowed work requests */
 		varnish_submit_derive (conf->instance, "workers", "total_requests", "overflowed", stats->n_wrk_overflow);
-#else /* HAVE_VARNISH_V3 */
-		/* queued work requests */
-		varnish_submit_derive (conf->instance, "workers", "total_requests", "queued",       stats->n_wrk_queued);
-		/* work request queue length */
-		varnish_submit_derive (conf->instance, "workers", "total_requests", "queue_length", stats->n_wrk_lqueue);
-#endif
-#endif
-	}
-
-#if HAVE_VARNISH_V4
-	if (conf->collect_vsm)
-	{
-		/* Free VSM space */
-		varnish_submit_gauge (conf->instance, "vsm", "bytes", "free",              stats->vsm_free);
-		/* Used VSM space */
-		varnish_submit_gauge (conf->instance, "vsm", "bytes", "used",              stats->vsm_used);
-		/* Cooling VSM space */
-		varnish_submit_gauge (conf->instance, "vsm", "bytes", "cooling",           stats->vsm_cooling);
-		/* Overflow VSM space */
-		varnish_submit_gauge (conf->instance, "vsm", "bytes", "overflow",          stats->vsm_overflow);
-		/* Total overflowed VSM space */
-		varnish_submit_derive (conf->instance, "vsm", "total_bytes", "overflowed", stats->vsm_overflowed);
 	}
-#endif
 
 } /* }}} void varnish_monitor */
+#endif
 
 #if HAVE_VARNISH_V3 || HAVE_VARNISH_V4
 static int varnish_read (user_data_t *ud) /* {{{ */
@@ -632,8 +837,12 @@ static int varnish_read (user_data_t *ud
 	stats = VSC_Main(vd, NULL);
 #endif
 
-	varnish_monitor (conf, stats);
-	VSM_Close (vd);
+#if HAVE_VARNISH_V3
+	VSC_Iter (vd, varnish_monitor, conf);
+#else /* if HAVE_VARNISH_V4 */
+	VSC_Iter (vd, NULL, varnish_monitor, conf);
+#endif
+        VSM_Delete (vd);
 
 	return (0);
 } /* }}} */
