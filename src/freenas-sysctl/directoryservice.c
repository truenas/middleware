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
#include <sys/systm.h>
#include <sys/sysctl.h>

#include "freenas_sysctl.h"
#include "utils.h"

#include "directoryservice.h"

static struct {
#define DSSTRSIZE	1024

	struct service_timeout ds_st;
	struct service_error ds_se;

	struct {
		struct service_timeout ds_st;
		struct service_error ds_se;
		struct {
			unsigned long lifetime;
			unsigned long timeout;
		} dns;
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

static int
directoryservice_init(void)
{
	struct sysctl_oid *dstree, *tmptree, *tmptree2;

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

	if ((tmptree2 = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(tmptree), OID_AUTO,
		"dns", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add directoryservice DNS node.\n", -1);
	}
	SYSCTL_ADD_LONG(&g_freenas_sysctl_ctx, SYSCTL_CHILDREN(tmptree2), OID_AUTO,
		"lifetime", CTLFLAG_RW, &g_directoryservice->activedirectory.dns.lifetime, "DNS lifetime");
	SYSCTL_ADD_LONG(&g_freenas_sysctl_ctx, SYSCTL_CHILDREN(tmptree2), OID_AUTO,
		"timeout", CTLFLAG_RW,  &g_directoryservice->activedirectory.dns.timeout, "DNS timeout");

	g_directoryservice->activedirectory.dns.timeout = 5;
	g_directoryservice->activedirectory.dns.lifetime = 5;


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
directoryservice_fini(void)
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

static struct freenas_sysctl_module _directoryservice_module = {
	"directoryservice", directoryservice_init, directoryservice_fini
};

struct freenas_sysctl_module *
directoryservice_module(void)
{
	return &_directoryservice_module;
}
