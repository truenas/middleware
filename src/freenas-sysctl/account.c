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

#include "account.h"

static struct {
	struct service_timeout a_st;
	struct service_error a_se;

	struct {
		struct service_timeout a_st;
		struct service_error a_se;
	} user;

} *g_account;

static int
account_init(void)
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
account_fini(void)
{
	free(g_account, M_FREENAS_SYSCTL);
	return (0);
}

static struct freenas_sysctl_module _account_module = {
	"account", account_init, account_fini
};

struct freenas_sysctl_module *
account_module(void)
{
	return &_account_module;
}
