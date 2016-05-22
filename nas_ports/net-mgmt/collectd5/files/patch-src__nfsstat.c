--- src/nfsstat.c.orig	2016-05-22 07:00:21 UTC
+++ src/nfsstat.c
@@ -0,0 +1,201 @@
+/**
+ * collectd - src/nfs_freebsd.c 
+ * 
+ * Copyright (c) 2016 iXsystems, Inc.
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
+ */
+
+#include "collectd.h"
+#include "common.h"
+#include "plugin.h"
+
+#include <sys/param.h>
+#include <sys/module.h>
+#include <sys/mount.h>
+#include <nfs/nfsproto.h>
+#include <nfsclient/nfs.h>
+#include <nfsserver/nfs.h>
+#include <nfs/nfssvc.h>
+#include <fs/nfs/nfsport.h>
+
+#define	NFSSTAT_CLIENT_ONLY		0x00000001
+#define	NFSSTAT_SERVER_ONLY		0x00000002
+#define	NFSSTAT_PERCENTAGE		0x00000004
+#define	NFSSTAT_ALL				(NFSSTAT_CLIENT_ONLY|NFSSTAT_SERVER_ONLY)
+
+
+#if 0
+static int
+nfsstat_config(const char *key, const char *value)
+{
+	return (0);
+}
+#endif
+
+
+static int
+nfsstat_init(void)
+{
+	return (0);
+}
+
+static int
+nfsstat_submit(struct ext_nfsstats *ext_nfsstats, uint64_t flags)
+{
+	_Bool percentage = 0;
+
+	if (flags & NFSSTAT_PERCENTAGE)
+		percentage = 1;
+
+	if (flags & NFSSTAT_CLIENT_ONLY) {
+		plugin_dispatch_multivalue(&vl, percentage, DS_TYPE_DERIVE,
+			"access", ext_nfsstats.rpccnt[NFSPROC_ACCESS],
+			"commit", ext_nfsstats.rpccnt[NFSPROC_COMMIT],
+			"create", ext_nfsstats.rpccnt[NFSPROC_CREATE],
+			"fsinfo", ext_nfsstats.rpccnt[NFSPROC_FSINFO],
+			"fsstat", ext_nfsstats.rpccnt[NFSPROC_FSSTAT],
+			"getattr", ext_nfsstats.rpccnt[NFSPROC_GETATTR],
+			"link", ext_nfsstats.rpccnt[NFSPROC_LINK],
+			"lookup", ext_nfsstats.rpccnt[NFSPROC_LOOKUP],
+			"mkdir", ext_nfsstats.rpccnt[NFSPROC_MKDIR],
+			"mknod", ext_nfsstats.rpccnt[NFSPROC_MKNOD],
+			"pathconf", ext_nfsstats.rpccnt[NFSPROC_PATHCONF],
+			"read", ext_nfsstats.rpccnt[NFSPROC_READ],
+			"readdir", ext_nfsstats.rpccnt[NFSPROC_READDIR],
+			"readirplus", ext_nfsstats.rpccnt[NFSPROC_READDIRPLUS],
+			"readlink", ext_nfsstats.rpccnt[NFSPROC_READLINK],
+			"remove", ext_nfsstats.rpccnt[NFSPROC_REMOVE],
+			"rename", ext_nfsstats.rpccnt[NFSPROC_RENAME],
+			"rmdir", ext_nfsstats.rpccnt[NFSPROC_RMDIR],
+			"setattr", ext_nfsstats.rpccnt[NFSPROC_SETATTR],
+			"symlink", ext_nfsstats.rpccnt[NFSPROC_SYMLINK],
+			"write", ext_nfsstats.rpccnt[NFSPROC_WRITE],
+			NULL
+		);
+	}
+
+#if 0
+	"TimedOut", ext_nfsstats.rpctimeouts
+	"Invalid", ext_nfsstats.rpcinvalid
+	"X Replies", ext_nfsstats.rpcunexpected
+	"Retries", ext_nfsstats.rpcretries
+	"Requests", ext_nfsstats.rpcrequests
+
+	"Attr Hits", ext_nfsstats.attrcache_hits
+	"Misses", ext_nfsstats.attrcache_misses
+	"Lookup Hits", ext_nfsstats.lookupcache_hits
+	"Misses", ext_nfsstats.lookupcache_misses
+
+	"BioR Hits", ext_nfsstats.read_bios
+	"Misses", ext_nfsstats.read_bios
+	"BioW Hits", ext_nfsstats.biocache_writes - ext_nfsstats.write_bios
+	"Misses", ext_nfsstats.write_bios
+
+	"BioRLHits", ext_nfsstats.biocache_readlinks - ext_nfsstats.readlink_bios
+	"Misses", ext_nfsstats.readlink_bios
+	"BioD Hists", ext_nfsstats.biocache_readdirs - ext_nfsstats.readdir_bios
+	"Misses", ext_nfsstats.readdir_bios
+
+	"DirE Hits", ext_nfsstats.direofcache_hits
+	"Misses", ext_nfsstats.direofcache_misses
+	"Accs Hits", ext_nfsstats.accesscache_hits
+	"Misses", ext_nfsstats.accesscache_misses
+#endif
+
+	if (flags & NFSSTAT_SERVER_ONLY) {
+		plugin_dispatch_multivalue(&vl, percentage, DS_TYPE_DERIVE,
+			"access", ext_nfsstats.srvrpccnt[NFSV4OP_ACCESS],
+			"commit", ext_nfsstats.srvrpccnt[NFSV4OP_COMMIT],
+			"create", ext_nfsstats.srvrpccnt[NFSV4OP_CREATE],
+			"fsinfo", ext_nfsstats.srvrpccnt[NFSV4OP_FSINFO],
+			"fsstat", ext_nfsstats.srvrpccnt[NFSV4OP_FSSTAT],
+			"getattr", ext_nfsstats.srvrpccnt[NFSV4OP_GETATTR],
+			"link", ext_nfsstats.srvrpccnt[NFSV4OP_LINK],
+			"lookup", ext_nfsstats.srvrpccnt[NFSV4OP_LOOKUP],
+			"mkdir", ext_nfsstats.srvrpccnt[NFSV4OP_MKDIR],
+			"mknod", ext_nfsstats.srvrpccnt[NFSV4OP_MKNOD],
+			"pathconf", ext_nfsstats.srvrpccnt[NFSV4OP_PATHCONF],
+			"read", ext_nfsstats.srvrpccnt[NFSV4OP_READ],
+			"readdir", ext_nfsstats.srvrpccnt[NFSV4OP_READDIR],
+			"readirplus", ext_nfsstats.srvrpccnt[NFSV4OP_READDIRPLUS],
+			"readlink", ext_nfsstats.srvrpccnt[NFSV4OP_READLINK],
+			"remove", ext_nfsstats.srvrpccnt[NFSV4OP_REMOVE],
+			"rename", ext_nfsstats.srvrpccnt[NFSV4OP_RENAME],
+			"rmdir", ext_nfsstats.srvrpccnt[NFSV4OP_RMDIR],
+			"setattr", ext_nfsstats.srvrpccnt[NFSV4OP_SETATTR],
+			"symlink", ext_nfsstats.srvrpccnt[NFSV4OP_SYMLINK],
+			"write", ext_nfsstats.srvrpccnt[NFSV4OP_WRITE],
+			NULL
+		);
+	}
+
+#if 0
+	"Server Ret-Failed", ext_nfsstats.srvrpc_errs
+	"Server Faults", ext_nfsstats.srv_errs
+
+	"Inprog", ext_nfsstats.srvcache_inproghits
+	"Idem", ext_nfsstats.srvcache_idemdonehits
+	"Non-idem", ext_nfsstats.srvcache_nonidemdonehits
+	"Misses", ext_nfsstats.srvcache_misses
+
+	"WriteOps", ext_nfsstats.srvrpccnt[NFSV4OP_WRITE]
+	"WriteRPC", ext_nfsstats.srvrpccnt[NFSV4OP_WRITE]
+#endif
+	}
+
+	return (0);
+}
+
+static int
+nfsstat_read(void)
+{
+	//char plugin_instance[DATA_MAX_NAME_LEN];
+	struct ext_nfsstats ext_nfsstats;
+
+	/* Get all stats for now */
+	bzero(&ext_nfsstats, sizeof(ext_nfsstats));
+	if (nfssvc(NFSSVC_GETSTATS, &ext_nfsstats) < 0) {
+		ERROR("nfssvc: Could not read NFS statistics");
+		return (-1);
+	}
+
+/*
+    ssnprintf (plugin_instance, sizeof (plugin_instance), "v%i%s",
+            nfs_version, instance);
+*/
+
+	nfsstat_submit(&ext_nfsstats, NFSSTAT_CLIENT_ONLY);
+	return (0);
+}
+
+void
+module_register(void)
+{
+#if 0
+	plugin_register_config("nfsstat", "nfsstat_config",
+		nfsstat_config_keys, nfsstat_config_keys_size);
+#endif
+	plugin_register_init("nfsstat", nfsstat_init);
+	plugin_register_read("nfsstat", nfsstat_read);
+} /* void module_register */
