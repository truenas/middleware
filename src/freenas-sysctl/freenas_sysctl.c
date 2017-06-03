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
#include <sys/module.h>
#include <sys/kernel.h>
#include <sys/queue.h>
#include <sys/systm.h>
#include <sys/sysctl.h>

#include "account.h"
#include "directoryservice.h"
#include "middlewared.h"
#include "network.h"
#include "services.h"
#include "utils.h"

#include "freenas_sysctl.h"

/*
 * We can build freenas release version string using git
 * hash and then create readonly system sysctl for it.
 *
 * eg: FreeNAS-9.10-MASTER-201704100409 (6c3a39d)
 *
 * Coming soon.
 *
 */
#define	FREENAS_VERSION	"FreeNAS-11-MASTER"
#define	MODULE_NAME	"freenas_sysctl"

MALLOC_DEFINE(M_FREENAS_SYSCTL,
	"freenas_sysctl", "FreeNAS sysctl configuration");

struct fsm_entry {
	struct freenas_sysctl_module *fsm;
    TAILQ_ENTRY(fsm_entry) entries;
};

TAILQ_HEAD(fsmhead, fsm_entry) g_freenas_sysctl_modules;

struct sysctl_ctx_list g_freenas_sysctl_ctx;
struct sysctl_oid *g_freenas_sysctl_tree;

/*
 *  Top level nodes (ideally): Document this
 *
 *  freenas.account
 *  freenas.debug
 *  freenas.directoryservice
 *  freenas.jails
 *  freenas.midddleware
 *  freenas.midddlewared
 *  freenas.network
 *  freenas.plugins
 *  freenas.reporting
 *  freenas.services
 *  freenas.sharing
 *  freenas.storage
 *  freenas.system
 *  freenas.tasks
 *  freenas.vms
 */

void
freenas_sysctl_add_module(struct freenas_sysctl_module *m)
{
	if (m != NULL) {
		printf("%s: adding %s.\n", MODULE_NAME, m->name);

		struct fsm_entry *entry = malloc(sizeof(*entry),
			M_FREENAS_SYSCTL, M_ZERO | M_WAITOK);
		entry->fsm = m;
		TAILQ_INSERT_TAIL(&g_freenas_sysctl_modules, entry, entries);
	}
}

void
freenas_sysctl_remove_module(struct freenas_sysctl_module *m)
{
	if (m != NULL) {
		struct fsm_entry *entry, *tmp;

		printf("%s: removing %s.\n", MODULE_NAME, m->name);
		TAILQ_FOREACH_SAFE(entry, &g_freenas_sysctl_modules, entries, tmp) {
			if (m == entry->fsm) {
				free(m, M_FREENAS_SYSCTL);
			}
		}
	}
}


static void
freenas_sysctl_setup(void)
{
	TAILQ_INIT(&g_freenas_sysctl_modules);

	freenas_sysctl_add_module(account_module());
	freenas_sysctl_add_module(directoryservice_module());
	freenas_sysctl_add_module(middlewared_module());
	freenas_sysctl_add_module(network_module());
	freenas_sysctl_add_module(services_module());
}

static void
freenas_sysctl_teardown(void)
{
	struct fsm_entry *entry, *tmp;

	TAILQ_FOREACH_REVERSE_SAFE(entry, &g_freenas_sysctl_modules, fsmhead, entries, tmp) {
		free(entry, M_FREENAS_SYSCTL);
	}
}

static int
freenas_sysctl_init(void)
{
	int error = 0;
	struct fsm_entry *entry;

	TAILQ_FOREACH(entry, &g_freenas_sysctl_modules, entries) {
		struct freenas_sysctl_module *m = entry->fsm;

		if (m == NULL)
			continue;
		if (m->initfunc == NULL)
			continue;
		if (m->initfunc() != 0)
			error = EINVAL;
	}

	return (error);
}

static int
freenas_sysctl_fini(void)
{
	int error = 0;
	struct fsm_entry *entry;

	TAILQ_FOREACH_REVERSE(entry, &g_freenas_sysctl_modules, fsmhead, entries) {
		struct freenas_sysctl_module *m = entry->fsm;

		if (m == NULL)
			continue;
		if (m->finifunc == NULL)
			continue;
		if (m->finifunc() != 0)
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
			freenas_sysctl_setup();

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

			freenas_sysctl_teardown();
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
