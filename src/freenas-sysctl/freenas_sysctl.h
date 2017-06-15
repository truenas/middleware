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

#ifndef	__FREENAS_SYSCTL_H
#define	__FREENAS_SYSCTL_H

#include <sys/param.h>
#include <sys/malloc.h>
#include <sys/kernel.h>
#include <sys/systm.h>
#include <sys/sysctl.h>

MALLOC_DECLARE(M_FREENAS_SYSCTL);

struct freenas_sysctl_module {
	char *name;
	int (*initfunc)(void);
	int (*finifunc)(void);
};

struct fstring {
	char *value;
	size_t size;
};

struct service_timeout {
	unsigned long start;
	unsigned long stop;
	unsigned long started;
	unsigned long restart;
	unsigned long reload;
};

struct service_error {
	struct fstring last_error;
};

extern struct sysctl_ctx_list g_freenas_sysctl_ctx;
extern struct sysctl_oid *g_freenas_sysctl_tree;

void freenas_sysctl_add_module(struct freenas_sysctl_module *);
void freenas_sysctl_remove_module(struct freenas_sysctl_module *);

#endif /* __FREENAS_SYSCTL_H */
