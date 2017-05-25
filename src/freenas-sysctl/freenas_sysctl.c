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

/*
 * FreeNAS configuration sysctl driver
 *
 * The idea here is to store advanced congiruation using sysctl.
 * Currently, only timeouts for services and directory services are
 * stored, but going forward, we will want to store things like HA state,
 * release name, and debugging knobs here as well. This skeleton is
 * enough to make things easy to add to in the future ;-)
 *
 */

#include <sys/param.h>
#include <sys/malloc.h>
#include <sys/module.h>
#include <sys/kernel.h>
#include <sys/systm.h>
#include <sys/sysctl.h>

/*
 * We can build freenas release version string using git
 * hash and then create readonly system sysctl for it.
 *
 * eg: FreeNAS-9.10-MASTER-201704100409 (6c3a39d)
 *
 * Coming soon.
 *
 */
#define	FREENAS_VERSION	"FreeNAS-9.10-MASTER"
#define	MODULE_NAME	"freenas_sysctl"
#define FAILRET(msg, ret) do { \
	printf("%s: %s", __FUNCTION__, msg); \
	return (ret); \
} while (0)

static MALLOC_DEFINE(M_FREENAS_SYSCTL,
	"freenas_sysctl", "FreeNAS sysctl configuration");

static struct sysctl_ctx_list g_freenas_sysctl_ctx;
static struct sysctl_oid *g_freenas_sysctl_tree;

struct fstring {
	char *value;
	size_t size;
};

struct service_timeout {
	unsigned long start;
	unsigned long stop;
	unsigned long restart;
	unsigned long reload;
};

struct service_error {
	struct fstring last_error;
};


static struct {
	struct service_timeout a_st;
	struct service_error a_se;

	struct {
		struct service_timeout a_st;
		struct service_error a_se;
	} user;

} *g_account;

static struct {
#define DSSTRSIZE	1024

	struct service_timeout ds_st;
	struct service_error ds_se;

	struct {
		struct service_timeout ds_st;
		struct service_error ds_se;
	} activedirectory;

	struct {
		struct service_timeout ds_st;
		struct service_error ds_se;
	} ldap;

	struct nt4 {
		struct service_timeout ds_st;
		struct service_error ds_se;
	} nt4;

	struct nis {
		struct service_timeout ds_st;
		struct service_error ds_se;
	} nis;

	struct kerberos {
		struct service_timeout ds_st;
		struct service_error ds_se;
	} kerberos;
	
} *g_directoryservice;

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

	struct {
		struct service_timeout s_st;
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

static struct {
	struct service_timeout n_st;

	struct {
		struct service_timeout n_st;
		struct {
			struct service_timeout n_st;
		} sync;
	} interface;

} *g_network;

/*
 *	Top level nodes:
 *
 *	freenas.account
 *	freenas.debug
 *	freenas.directoryservice
 *	freenas.network
 *	freenas.jails
 *	freenas.plugins
 *	freenas.reporting
 *	freenas.services
 *	freenas.sharing
 *	freenas.storage
 *	freenas.system
 *	freenas.tasks
 *	freenas.vms
 */


static int
freenas_sysctl_add_timeout_tree(struct sysctl_ctx_list *ctx,
	struct sysctl_oid *root, struct service_timeout *st)
{
	struct sysctl_oid *timeout;

	if ((timeout = SYSCTL_ADD_NODE(ctx, SYSCTL_CHILDREN(root),
		OID_AUTO, "timeout", CTLFLAG_RW, NULL, NULL)) == NULL) {
		return (-1);
	}

	st->start = 30;
	st->stop = 30;
	st->restart = 30;
	st->reload = 30;

	SYSCTL_ADD_LONG(ctx, SYSCTL_CHILDREN(timeout), OID_AUTO,
		"start", CTLFLAG_RW, &st->start, "start timeout");
	SYSCTL_ADD_LONG(ctx, SYSCTL_CHILDREN(timeout), OID_AUTO,
		"stop", CTLFLAG_RW, &st->stop, "stop timeout");
	SYSCTL_ADD_LONG(ctx, SYSCTL_CHILDREN(timeout), OID_AUTO,
		"restart", CTLFLAG_RW, &st->restart, "restart timeout");
	SYSCTL_ADD_LONG(ctx, SYSCTL_CHILDREN(timeout), OID_AUTO,
		"reload", CTLFLAG_RW, &st->reload, "reload timeout");

	return (0);
}

static int
freenas_sysctl_add_error_tree(struct sysctl_ctx_list *ctx,
	struct sysctl_oid *root, struct service_error *se)
{
	struct sysctl_oid *errortree;

	if ((errortree = SYSCTL_ADD_NODE(ctx, SYSCTL_CHILDREN(root),
		OID_AUTO, "error", CTLFLAG_RW, NULL, NULL)) == NULL) {
		return (-1);
	}

	SYSCTL_ADD_STRING(ctx, SYSCTL_CHILDREN(errortree), OID_AUTO,
		"last_error", CTLFLAG_RW, se->last_error.value,
		se->last_error.size, "last error message");

	return (0);
}

static int
freenas_sysctl_account_init(void)
{
	struct sysctl_oid *stree, *tmptree;

	g_account = malloc(sizeof(*g_account),
		M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);

	/* Account node */
	if ((stree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(g_freenas_sysctl_tree), OID_AUTO,
		"account", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add account node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		stree, &g_account->a_st)) != 0) {
		FAILRET("Failed to add account timeout node.\n", -1);
	}

	/* User node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(stree), OID_AUTO,
		"user", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add user node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_account->user.a_st)) != 0) {
		FAILRET("Failed to add user timeout node.\n", -1);
	}

	return (0);
}

static int
freenas_sysctl_account_fini(void)
{
	free(g_account, M_FREENAS_SYSCTL);
	return (0);
}

static int
freenas_sysctl_debug_init(void)
{
	return (0);
}

static int
freenas_sysctl_debug_fini(void)
{
	return (0);
}

static int
freenas_sysctl_directoryservice_init(void)
{
	struct sysctl_oid *dstree, *tmptree;

	/* TODO: break into functions for each tree */

	/* Directory service memory allocations */
	g_directoryservice = malloc(sizeof(*g_directoryservice),
		M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);
	g_directoryservice->ds_se.last_error.value = \
		malloc(DSSTRSIZE, M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);
	g_directoryservice->ds_se.last_error.size = DSSTRSIZE;

	/* Active Directory memory allocations */
	g_directoryservice->activedirectory.ds_se.last_error.value = \
		malloc(DSSTRSIZE, M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);
	g_directoryservice->activedirectory.ds_se.last_error.size = DSSTRSIZE;

	/* LDAP memory allocations */
	g_directoryservice->ldap.ds_se.last_error.value = \
		malloc(DSSTRSIZE, M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);
	g_directoryservice->ldap.ds_se.last_error.size = DSSTRSIZE;

	/* Kerberos memory allocations */
	g_directoryservice->kerberos.ds_se.last_error.value = \
		malloc(DSSTRSIZE, M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);
	g_directoryservice->kerberos.ds_se.last_error.size = DSSTRSIZE;


	/* Directory Service node */
	if ((dstree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(g_freenas_sysctl_tree), OID_AUTO,
		"directoryservice", CTLFLAG_RW, NULL, NULL)) == NULL) {
		FAILRET("Failed to add directoryservice node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		dstree, &g_directoryservice->ds_st)) != 0) {
		FAILRET("Failed to add directoryservice timeout node.\n", -1);
	}
	if ((freenas_sysctl_add_error_tree(&g_freenas_sysctl_ctx,
		dstree, &g_directoryservice->ds_se)) != 0) {
		FAILRET("Failed to add directoryservice error node.\n", -1);
	}

	/* Active Directory node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(dstree), OID_AUTO,
		"activedirectory", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add activedirectory node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_directoryservice->activedirectory.ds_st)) != 0) {
		FAILRET("Failed to add activedirectory timeout node.\n", -1);
	}
	if ((freenas_sysctl_add_error_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_directoryservice->activedirectory.ds_se)) != 0) {
		FAILRET("Failed to add activedirectory error node.\n", -1);
	}

	g_directoryservice->activedirectory.ds_st.start = 90;
	g_directoryservice->activedirectory.ds_st.stop = 90;
	g_directoryservice->activedirectory.ds_st.restart = 180;
	g_directoryservice->activedirectory.ds_st.reload = 180;


	/* LDAP node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(dstree), OID_AUTO,
		"ldap", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add ldap node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_directoryservice->ldap.ds_st)) != 0) {
		FAILRET("Failed to add ldap timeout node.\n", -1);
	}
	if ((freenas_sysctl_add_error_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_directoryservice->ldap.ds_se)) != 0) {
		FAILRET("Failed to add ldap error node.\n", -1);
	}

	g_directoryservice->ldap.ds_st.start = 90;
	g_directoryservice->ldap.ds_st.stop = 90;
	g_directoryservice->ldap.ds_st.restart = 180;
	g_directoryservice->ldap.ds_st.reload = 180;


	/* NT4 node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(dstree), OID_AUTO,
		"nt4", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add nt4 node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_directoryservice->nt4.ds_st)) != 0) {
		FAILRET("Failed to add nt4 timeout node.\n", -1);
	}

	/* NIS node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(dstree), OID_AUTO,
		"nis", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add nis node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_directoryservice->nis.ds_st)) != 0) {
		FAILRET("Failed to add nis timeout node.\n", -1);
	}

	/* Kerberos node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(dstree), OID_AUTO,
		"kerberos", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add kerberos node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_directoryservice->kerberos.ds_st)) != 0) {
		FAILRET("Failed to add kerberos timeout node.\n", -1);
	}
	if ((freenas_sysctl_add_error_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_directoryservice->kerberos.ds_se)) != 0) {
		FAILRET("Failed to add kerberos error node.\n", -1);
	}

	return (0);
}

static int
freenas_sysctl_directoryservice_fini(void)
{
	free(g_directoryservice->kerberos.ds_se.last_error.value,
		M_FREENAS_SYSCTL);
	free(g_directoryservice->ldap.ds_se.last_error.value,
		M_FREENAS_SYSCTL);
	free(g_directoryservice->activedirectory.ds_se.last_error.value,
		M_FREENAS_SYSCTL);
	free(g_directoryservice->ds_se.last_error.value,
		M_FREENAS_SYSCTL);
	free(g_directoryservice, M_FREENAS_SYSCTL);
	return (0);
}

static int
freenas_sysctl_network_init(void)
{
	struct sysctl_oid *ntree, *ifacetree, *tmptree;

	/* Network memory allocations */
	g_network = malloc(sizeof(*g_network),
		M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);

	/* Network node */
	if ((ntree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(g_freenas_sysctl_tree), OID_AUTO,
		"network", CTLFLAG_RW, NULL, NULL)) == NULL) {
		FAILRET("Failed to add network node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		ntree, &g_network->n_st)) != 0) {
		FAILRET("Failed to add network timeout node.\n", -1);
	}

	/* Network interface node */
	if ((ifacetree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(ntree), OID_AUTO,
		"interface", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add network interface node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		ifacetree, &g_network->interface.n_st)) != 0) {
		FAILRET("Failed to add network interface timeout node.\n", -1);
	}

	/* Network interface sync node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(ifacetree), OID_AUTO,
		"sync", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add network interface sync node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		tmptree, &g_network->interface.sync.n_st)) != 0) {
		FAILRET("Failed to add network interface sync timeout node.\n", -1);
	}

	return (0);
}

static int
freenas_sysctl_network_fini(void)
{
	free(g_network, M_FREENAS_SYSCTL);
	return (0);
}

static int
freenas_sysctl_jails_init(void)
{
	return (0);
}

static int
freenas_sysctl_jails_fini(void)
{
	return (0);
}

static int
freenas_sysctl_plugins_init(void)
{
	return (0);
}

static int
freenas_sysctl_plugins_fini(void)
{
	return (0);
}

static int
freenas_sysctl_reporting_init(void)
{
	return (0);
}

static int
freenas_sysctl_reporting_fini(void)
{
	return (0);
}

static int
freenas_sysctl_services_init(void)
{
	struct sysctl_oid *stree, *tmptree;

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
freenas_sysctl_services_fini(void)
{
	free(g_services, M_FREENAS_SYSCTL);
	return (0);
}

static int
freenas_sysctl_sharing_init(void)
{
	return (0);
}

static int
freenas_sysctl_sharing_fini(void)
{
	return (0);
}

static int
freenas_sysctl_storage_init(void)
{
	return (0);
}

static int
freenas_sysctl_storage_fini(void)
{
	return (0);
}

static int
freenas_sysctl_system_init(void)
{
	return (0);
}

static int
freenas_sysctl_system_fini(void)
{
	return (0);
}

static int
freenas_sysctl_tasks_init(void)
{
	return (0);
}

static int
freenas_sysctl_tasks_fini(void)
{
	return (0);
}

static int
freenas_sysctl_vms_init(void)
{
	return (0);
}

static int
freenas_sysctl_vms_fini(void)
{
	return (0);
}

static struct {
	int (*initfunc)(void);
	int (*finifunc)(void);
} freenas_sysctl_funcs[] = {
	{ freenas_sysctl_account_init,
		freenas_sysctl_account_fini },
	{ freenas_sysctl_debug_init,
		freenas_sysctl_debug_fini },
	{ freenas_sysctl_directoryservice_init,
		freenas_sysctl_directoryservice_fini },
	{ freenas_sysctl_network_init,
		freenas_sysctl_network_fini },
	{ freenas_sysctl_jails_init,
		freenas_sysctl_jails_fini },
	{ freenas_sysctl_plugins_init,
		freenas_sysctl_plugins_fini },
	{ freenas_sysctl_reporting_init,
		freenas_sysctl_reporting_fini },
	{ freenas_sysctl_services_init,
		freenas_sysctl_services_fini },
	{ freenas_sysctl_sharing_init,
		freenas_sysctl_sharing_fini },
	{ freenas_sysctl_storage_init,
		freenas_sysctl_storage_fini },
	{ freenas_sysctl_system_init,
		freenas_sysctl_system_fini },
	{ freenas_sysctl_tasks_init,
		freenas_sysctl_tasks_fini },
	{ freenas_sysctl_vms_init,
		freenas_sysctl_vms_fini }
};
static size_t freenas_sysctl_funcs_size = \
	sizeof(freenas_sysctl_funcs) / sizeof(freenas_sysctl_funcs[0]);


static int
freenas_sysctl_init(void)
{
	int i, error = 0;

	for (i = 0;i < freenas_sysctl_funcs_size;i++) {
		if (freenas_sysctl_funcs[i].initfunc() != 0)
			error = EINVAL;
	}

	return (error);
}

static int
freenas_sysctl_fini(void)
{
	int i, error = 0;

	for (i = 0;i < freenas_sysctl_funcs_size;i++) {
		if (freenas_sysctl_funcs[i].finifunc() != 0)
			error = EINVAL;
	}

	return (error);
}

static int
freenas_sysctl_modevent(module_t mod, int type, void *data)
{
	int error = 0;

	switch (type) {
		case MOD_LOAD:
			if (sysctl_ctx_init(&g_freenas_sysctl_ctx) != 0) {
				printf("%s: sysctl_ctx_init failed.\n", MODULE_NAME);
				return (EINVAL);
			}

			g_freenas_sysctl_tree = SYSCTL_ADD_ROOT_NODE(&g_freenas_sysctl_ctx,
				OID_AUTO, "freenas", CTLFLAG_RW, 0, "freenas root node");
			if (g_freenas_sysctl_tree == NULL) {
				printf("%s: SYSCTL_ADD_ROOT_NODE failed.\n", MODULE_NAME);
				return (EINVAL);
			}

			if (freenas_sysctl_init() != 0) {
				freenas_sysctl_fini();
				sysctl_ctx_free(&g_freenas_sysctl_ctx);
				return (EINVAL);
			}

			break;

		case MOD_UNLOAD:
			freenas_sysctl_fini();
			if (sysctl_ctx_free(&g_freenas_sysctl_ctx) != 0) {
				printf("%s: sysctl_ctx_free failed.\n", MODULE_NAME);
				return (ENOTEMPTY);
			}

			break;

		case MOD_SHUTDOWN:
		case MOD_QUIESCE:
			break;

		default:
			error = EOPNOTSUPP;
			break;
	}

	return (error);
}

static moduledata_t freenas_sysctl_mod = {
	MODULE_NAME,
	freenas_sysctl_modevent,
	NULL
};

DECLARE_MODULE(freenas_sysctl, freenas_sysctl_mod, SI_SUB_EXEC, SI_ORDER_ANY);
