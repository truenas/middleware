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

#include "middlewared.h"

#if 0
static struct {
	struct service_timeout m_st;

} *g_middleware;
#endif

static struct {
	struct service_timeout m_st;

	struct {
		struct {
			unsigned long socket_timeout;
		} service_monitor;

	} plugins;

} *g_middlewared;

#if 0
static int
freenas_sysctl_middleware_init(void)
{
	g_middleware = NULL;
	return (0);
}

static int
freenas_sysctl_middleware_fini(void)
{
	return (0);
}
#endif

static int
middlewared_init(void)
{
	struct sysctl_oid *mtree, *tmptree, *tmptree2;

	/* Middlwared memory allocations */
	g_middlewared = malloc(sizeof(*g_middlewared),
		M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);

	/* Middlwared node */
	if ((mtree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(g_freenas_sysctl_tree), OID_AUTO,
		"middlewared", CTLFLAG_RW, NULL, NULL)) == NULL) {
		FAILRET("Failed to add network node.\n", -1);
	}
	if ((freenas_sysctl_add_timeout_tree(&g_freenas_sysctl_ctx,
		mtree, &g_middlewared->m_st)) != 0) {
		FAILRET("Failed to add network timeout node.\n", -1);
	}


	/* Middlewared plugins node */
	if ((tmptree = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(mtree), OID_AUTO,
		"plugins", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add middlewared node.\n", -1);
	}

	/* Middlewared plugins/service_monitor node */
	if ((tmptree2 = SYSCTL_ADD_NODE(&g_freenas_sysctl_ctx,
		SYSCTL_CHILDREN(tmptree), OID_AUTO,
		"service_monitor", CTLFLAG_RD, NULL, NULL)) == NULL) {
		FAILRET("Failed to add middlewared service_monitor node.\n", -1);
	}
	SYSCTL_ADD_LONG(&g_freenas_sysctl_ctx, SYSCTL_CHILDREN(tmptree2), OID_AUTO,
		"socket_timeout", CTLFLAG_RW,&g_middlewared->plugins.service_monitor.socket_timeout,
		"Socket timeout");

	g_middlewared->plugins.service_monitor.socket_timeout = 10;

	return (0);
}

static int
middlewared_fini(void)
{
	free(g_middlewared, M_FREENAS_SYSCTL);

	return (0);
}

static struct freenas_sysctl_module _middlewared_module = {
	"middlewared", middlewared_init, middlewared_fini
};

struct freenas_sysctl_module *
middlewared_module(void)
{
	return &_middlewared_module;
}
