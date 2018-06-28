/*-
 * Copyright 2018 iXsystems, Inc.
 * All rights reserved
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted providing that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
 * IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
 * DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
 * STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
 * IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 *
 */

#include <sys/types.h>
#include <sys/queue.h>
#include <sys/extattr.h>
#include <fcntl.h>
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sysexits.h>
#include <unistd.h>
#include <err.h>

#define EX_EA_CORRUPTED	1

struct xattr {
	char *name;
	void *value;
	size_t length;
	TAILQ_ENTRY(xattr) link;
};

TAILQ_HEAD(xattr_list, xattr);

void
usage(const char *path)
{
	fprintf(stderr,
		"Usage: %s [OPTIONS] <file>\n"
		"Where option is:\n"
		"     -c%16s# check if AFP extended attributes are corrupted (default)\n"
		"     -f%16s# fix AFP extended attributes\n"
		"     -v%16s# verbose\n\n"
		"Exit codes:\n"
		"      1 if corrupted\n"
		"      0 if not corrupted or fixed\n",
		path, " ", " ", " "
	);

	exit(EX_USAGE);
}


int
main(int argc, char **argv)
{
	int i, ch, fd, ret, setret, buflen;
	char *prog, *op, *path, *buf, *rp;
	struct xattr *xptr, *xtmp;
	struct xattr_list xlist;
	int check = 1, fix = 0, verbose = 0;

	prog = basename(argv[0]);
	if (argc < 2)
		usage(prog);

	while ((ch = getopt(argc, argv, "cfv")) != -1) {
		switch (ch) {
			case 'c':
				check = 1;
				fix = 0;
				break;
			case 'f':
				fix = 1;
				check = 0;	
				break;
			case 'v':
				verbose = 1;
				break;
			default:
				usage(prog);
		}
	}

	argc -= optind;		
	argv += optind;

	path = NULL;
	if (!isatty(STDIN_FILENO)) {
		ssize_t nread;	
		static char pathbuf[PATH_MAX];

		if ((nread = read(STDIN_FILENO, pathbuf, sizeof(pathbuf))) > 0) {
			pathbuf[nread - 1] = 0;
			path = &pathbuf[0];
		}
	}

	if (path == NULL && ((path = argv[0]) == NULL))
		usage(prog);

	if ((rp = realpath(path, NULL)) == NULL)
		err(EX_OSERR, "%s", path);

	if (access(rp, F_OK) != 0)
		err(EX_OSERR, "%s", path);

	if ((fd = open(rp, O_RDONLY)) < 0)
		err(EX_OSERR, "%s", path);

	if ((ret = extattr_list_fd(fd, EXTATTR_NAMESPACE_USER, NULL, 0)) < 0)
		return (EX_OK);

	if ((buf = malloc(ret)) == NULL)
		err(EX_OSERR, NULL);

	buflen = ret;
	if ((ret = extattr_list_fd(fd, EXTATTR_NAMESPACE_USER, buf, buflen)) < 0) {
		free(buf);
		free(rp);
		close(fd);
		err(EX_OSERR, NULL);
	}

	TAILQ_INIT(&xlist);

	for (i = 0;i < ret;i += ch + 1) {
		struct xattr *xptr;
		char *name, *value;
		int getret;

		ch = (unsigned char)buf[i];
		if ((name = malloc(ch)) == NULL) {
			err(EX_OSERR, NULL);
			continue;
		}

		strncpy(name, &buf[i + 1], ch);
		name[ch] = '\0';

		if ((getret = extattr_get_fd(fd, EXTATTR_NAMESPACE_USER,
			name, NULL, 0)) < 0) {
			free(name);
			continue;
		}

		if ((value = malloc(getret)) == NULL) {
			warn("malloc");	
			free(name);
			continue;
		}

		if ((getret = extattr_get_fd(fd, EXTATTR_NAMESPACE_USER,
			name, value, getret)) < 0) {
			free(value);
			free(name);
			continue;
		}

		if (!(value[0] == 0 && value[1] == 'F' && value[2] == 'P')) {
			free(value);
			free(name);
			continue;
		}

		if ((xptr = malloc(sizeof(*xptr))) == NULL) {
			warn("malloc");	
			continue;
		}

		bzero(xptr, sizeof(*xptr));
		xptr->name = name;
		xptr->value = value;
		xptr->length = getret;

		TAILQ_INSERT_HEAD(&xlist, xptr, link);
	}

	ret = 0;
	TAILQ_FOREACH_REVERSE(xptr, &xlist, xattr_list, link) {
		if (check) {
			ret |= EX_EA_CORRUPTED;
			if (verbose)
				printf("%s: %s is corrupted\n", path, xptr->name);
		}

		if (fix) {
			*((char *)xptr->value) = 'A';
			if ((setret = extattr_set_fd(fd, EXTATTR_NAMESPACE_USER,
				xptr->name, xptr->value, xptr->length)) < 0) {
				warn("extattr_set_fd");
				ret |= EX_EA_CORRUPTED;
			} 

			if (setret > 0) {
				ret |= EX_OK;
				if (verbose)
					printf("%s: %s is fixed\n", path, xptr->name);
			}
		}
	}

	TAILQ_FOREACH_SAFE(xptr, &xlist, link, xtmp) {
		TAILQ_REMOVE(&xlist, xptr, link);
		free(xptr->name);
		free(xptr->value);
		free(xptr);
	}

	free(buf);
	free(rp);
	close(fd);

	return (ret);
}
