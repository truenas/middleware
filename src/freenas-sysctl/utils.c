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

int
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

int
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
