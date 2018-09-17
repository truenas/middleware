/*-
 * Copyright (c) 2017 iXsystems, Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 */

#include <sys/param.h>
#include <sys/malloc.h>
#include <sys/module.h>
#include <sys/kernel.h>
#include <sys/sbuf.h>
#include <sys/systm.h>
#include <sys/sysctl.h>

#include "freenas_sysctl.h"
#include "utils.h"

#include "services.h"

static struct {
	struct service_timeout s_st;

	struct {
		struct service_timeout s_st;
	} afp;

	struct {
		struct service_timeout s_st;
	} dc;

	struct {
		struct service_timeout s_st;
	} ftp;

	struct {
		struct service_timeout s_st;
	} iscsi;

	struct {
		struct service_timeout s_st;
	} lldp;

	struct {
		struct service_timeout s_st;
	} nfs;

	struct {
		struct service_timeout s_st;
	} rsync;

	struct {
		struct service_timeout s_st;
	} s3;

	struct {
		struct service_timeout s_st;
	} smart;

	/*
	 * This should get its own file. We should add lots more
	 * performance tuning options here as well. Coming soon?
	 */
	struct {
		struct service_timeout s_st;
		struct {
			unsigned int server_min_protocol;
			unsigned int server_max_protocol;
			unsigned int server_multi_channel;
		} config;
	} smb;

	struct {
		struct service_timeout s_st;
	} snmp;

	struct {
		struct service_timeout s_st;
	} ssh;

	struct {
		struct service_timeout s_st;
	} tftp;

	struct {
		struct service_timeout s_st;
	} ups;

	struct {
		struct service_timeout s_st;
	} webdav;

} *g_services;

enum {
	CORE = 0,
	COREPLUS = 1,
	LANMAN1 = 2,
	LANMAN2 = 3,
	NT1 = 4,
	SMB2 = 5,
	SMB2_02 = 6,
	SMB2_10 = 7,
	SMB2_22 = 8,
	SMB2_24 = 9,
	SMB3 = 10,
	SMB3_00 = 11,
	SMB3_02 = 12,
	SMB3_10 = 13,
	SMB3_11 = 14,
	SMB_PROTO_NONE = 15,
	SMB_PROTO_COUNT = 16
};

static const char *SMB_PROTOS[] = {
	"CORE",
	"COREPLUS",
	"LANMAN1",
	"LANMAN2",
	"NT1",
	"SMB2",
	"SMB2_02",
	"SMB2_10",
	"SMB2_22",
	"SMB2_24",
	"SMB3",
	"SMB3_00",
	"SMB3_02",
	"SMB3_10",
	"SMB3_11",
	"NONE"
};

static int
smbname2proto(const char *name)
{
	int i;
	
	if (name == NULL)
		return (-1);

	for (i = CORE;i < SMB_PROTO_COUNT;i++) {
		if (strcasecmp(name, SMB_PROTOS[i]) == 0)
			return (i);
	}

	return (-1);
}

static const char *
smbproto2name(int proto)
{
	if (proto >= CORE && proto <= SMB3_11)
		return (SMB_PROTOS[proto]);

	return ("NONE");
}

static int
sysctl_smb_server_proto(SYSCTL_HANDLER_ARGS)
{
	char proto[FNBUFSIZ_32];
	int error, new_proto, old_proto;

	old_proto = *(int *)oidp->oid_arg1;
	strlcpy(proto, smbproto2name(old_proto), sizeof(proto));

	error = sysctl_handle_string(oidp, proto, sizeof(proto), req);
	if (error == 0 && req->newptr != NULL) {
		new_proto = smbname2proto(proto);
		if (new_proto < CORE)
			return (EINVAL);
		if (new_proto != old_proto)
			*(int *)oidp->oid_arg1 = new_proto;
	}

	return (error);
}

static int
services_init(void)
{
	struct sysctl_oid *stree, *tmptree, *tmptree2;

	g_services = malloc(sizeof(*g_services),
		M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);

	/* Services node */
	if ((stree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(g_freenas_sysctl_tree), OID_AUTO,
		"services", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add services node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		stree, &g_services->s_st)) != 0) {
		FAILRET("Failed to add services timeout node.\n", -1);
	}

	/* AFP node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"afp", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add afp node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->afp.s_st)) != 0) {
		FAILRET("Failed to add afp timeout node.\n", -1);
	}

	/* Domain Controller node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"domaincontroller", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add domain controller node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->dc.s_st)) != 0) {
		FAILRET("Failed to add domain controller timeout node.\n", -1);
	}

	g_services->dc.s_st.restart = 180;

	/* FTP node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"ftp", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add ftp node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->ftp.s_st)) != 0) {
		FAILRET("Failed to add ftp timeout node.\n", -1);
	}

	/* iSCSI node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"iscsi", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add iscsi node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->iscsi.s_st)) != 0) {
		FAILRET("Failed to add iscsi timeout node.\n", -1);
	}

	/* LLDP node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"lldp", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add lldp node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->lldp.s_st)) != 0) {
		FAILRET("Failed to add lldp timeout node.\n", -1);
	}

	/* NFS node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"nfs", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add nfs node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->nfs.s_st)) != 0) {
		FAILRET("Failed to add nfs timeout node.\n", -1);
	}

	/* Rsync node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"rsync", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add rsync node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->rsync.s_st)) != 0) {
		FAILRET("Failed to add rsync timeout node.\n", -1);
	}

	/* S3 node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"s3", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add s3 node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->s3.s_st)) != 0) {
		FAILRET("Failed to add s3 timeout node.\n", -1);
	}

	/* S.M.A.R.T. node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"smart", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add smart node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->smart.s_st)) != 0) {
		FAILRET("Failed to add smart timeout node.\n", -1);
	}

	/* SMB node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"smb", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add smb node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->smb.s_st)) != 0) {
		FAILRET("Failed to add smb timeout node.\n", -1);
	}

	g_services->smb.config.server_min_protocol = SMB2_02;
	g_services->smb.config.server_max_protocol = SMB3;
	g_services->smb.config.server_multi_channel = 0;

	/* SMB config */
	if ((tmptree2 = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(tmptree), OID_AUTO,
		"config", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add SMB config node.\n", -1);
	}
	
	SYSCTL_ADD_PROC(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(tmptree2), OID_AUTO,
		"server_min_protocol", CTLTYPE_STRING|CTLFLAG_RW,
		&g_services->smb.config.server_min_protocol, 0,
		sysctl_smb_server_proto, "A", "server min protocol");

	SYSCTL_ADD_PROC(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(tmptree2), OID_AUTO,
		"server_max_protocol", CTLTYPE_STRING|CTLFLAG_RW,
		&g_services->smb.config.server_max_protocol, 0,
		sysctl_smb_server_proto, "A", "server max protocol");

	SYSCTL_ADD_UINT(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(tmptree2), OID_AUTO,
		"server_multi_channel", CTLFLAG_RW,
		&g_services->smb.config.server_multi_channel, 0,
		"server multi channel support");

	/* SNMP node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"snmp", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add snmp node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->snmp.s_st)) != 0) {
		FAILRET("Failed to add snmp timeout node.\n", -1);
	}

	/* SSH node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"ssh", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add ssh node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->ssh.s_st)) != 0) {
		FAILRET("Failed to add ssh timeout node.\n", -1);
	}

	/* TFTP node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"tftp", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add tftp node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->tftp.s_st)) != 0) {
		FAILRET("Failed to add tftp timeout node.\n", -1);
	}

	/* UPS node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"ups", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add ups node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->ups.s_st)) != 0) {
		FAILRET("Failed to add ups timeout node.\n", -1);
	}

	/* WebDAV node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"webdav", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add webdav node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_services->webdav.s_st)) != 0) {
		FAILRET("Failed to add webdav timeout node.\n", -1);
	}

	return (0);
}

static int
services_fini(void)
{
	free(g_services, M_FREENAS_SYSCTL);
	return (0);
}

static struct freenas_sysctl_module _services_module = {
	"services", services_init, services_fini
};

struct freenas_sysctl_module *
services_module(void)
{
	return &_services_module;
}
