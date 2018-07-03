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

#define	F_NONE			0x0000
#define	F_APPEND_NULL_ALL	0x0001
#define	F_CHECK_AFP_EA		0x0002
#define	F_DRY_RUN		0x0004
#define	F_FIX_AFP_EA		0x0008
#define	F_APPEND_NULL		0x0010
#define F_VERBOSE		0x0020
#define F_DEBUG			0x0040

#define	AFP_EA_CORRUPTED(v)	(v[0] == 0 && v[1] == 'F' && v[2] == 'P')


struct xattr {
	char *name;
	char *value;
	size_t length;
	TAILQ_ENTRY(xattr) link;
	TAILQ_ENTRY(xattr) afp_link;
	TAILQ_ENTRY(xattr) append_link;
};

TAILQ_HEAD(xattr_list, xattr);

void
usage(const char *path)
{
	fprintf(stderr,
		"Usage: %s [OPTIONS] <file>\n"
		"Where option is:\n"
		"     -a%16s# append null byte to all extended attributes\n"
		"     -c%16s# check if AFP extended attributes are corrupted\n"
		"     -C%16s# dry run (no changes are made)\n"
		"     -d%16s# debug mode\n"
		"     -f%16s# fix AFP extended attributes\n"
		"     -n <EA>%11s# append null byte\n"
		"     -v%16s# verbose\n\n"
		"Exit codes:\n"
		"      1 if corrupted\n"
		"      0 if not corrupted or fixed\n",
		path, " ", " ", " ", " ", " ", " ", " "
	);

	exit(EX_USAGE);
}

int
get_extended_attributes(int fd, struct xattr_list *xlist)
{
	int i, ch, ret, buflen;
	char *path, *buf;

	if ((ret = extattr_list_fd(fd, EXTATTR_NAMESPACE_USER, NULL, 0)) < 0)
		return (EX_OK);

	if ((buf = malloc(ret)) == NULL) {
		warn("malloc");
		return (-1);
	}

	buflen = ret;
	if ((ret = extattr_list_fd(fd, EXTATTR_NAMESPACE_USER, buf, buflen)) < 0) {
		free(buf);
		warn("extattr_list_fd");
		return (-1);
	}

	for (i = 0;i < ret;i += ch + 1) {
		struct xattr *xptr = NULL;
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

		if ((xptr = malloc(sizeof(*xptr))) == NULL) {
			warn("malloc");	
			free(value);
			free(name);
			continue;
		}

		bzero(xptr, sizeof(*xptr));
		xptr->name = name;
		xptr->value = value;
		xptr->length = getret;

		TAILQ_INSERT_HEAD(xlist, xptr, link);
	}

	return (0);
}

int
get_afp_list(struct xattr_list *xlist, struct xattr_list *afp_list)
{
	struct xattr *xptr = NULL, *xtmp = NULL;

	if (xlist == NULL || afp_list == NULL)
		return (-1);

	TAILQ_FOREACH_REVERSE_SAFE(xptr, xlist, xattr_list, link, xtmp) {
		if (AFP_EA_CORRUPTED(xptr->value))
			TAILQ_INSERT_HEAD(afp_list, xptr, afp_link);
	}

	return (0);
}

int
fix_afp_list(int fd, const char *path,
		u_int64_t flags, struct xattr_list *afp_list)
{
	int ret = 0, setret = 0;
	struct xattr *xptr = NULL, *xtmp = NULL;

	if (afp_list == NULL)
		return (-1);

	TAILQ_FOREACH_REVERSE(xptr, afp_list, xattr_list, afp_link) {
		if (flags & F_DEBUG) {
			printf("%s: %02x %02x %02x / %02x %02x %02x [%ld]\n", path,
				(unsigned char)xptr->value[0],
				(unsigned char)xptr->value[1],
				(unsigned char)xptr->value[2],
				(unsigned char)xptr->value[xptr->length - 2],
				(unsigned char)xptr->value[xptr->length - 1],
				(unsigned char)xptr->value[xptr->length],
				xptr->length);
		}

		if (flags & F_CHECK_AFP_EA) {
			ret |= EX_EA_CORRUPTED;
			if (flags & F_VERBOSE) {
				printf("%s: %s is corrupted\n", path, xptr->name);
			}
		}

		if (flags & F_FIX_AFP_EA) {
			if ((flags & F_DRY_RUN) == 0) {
				*((char *)xptr->value) = 'A';
				if ((setret = extattr_set_fd(fd, EXTATTR_NAMESPACE_USER,
					xptr->name, xptr->value, xptr->length)) < 0) {
					warn("extattr_set_fd");
					ret |= EX_EA_CORRUPTED;
				} 
			}

			if (setret > 0 || flags & F_DRY_RUN) {
				ret |= EX_OK;
				if (flags & F_VERBOSE)
					printf("%s: %s is fixed\n", path, xptr->name);
			}
		}
	}

	return (ret);
}

void
unlink_afp_list(struct xattr_list *afp_list)
{
	if (afp_list != NULL) {
		struct xattr *xptr = NULL, *xtmp = NULL;

		TAILQ_FOREACH_SAFE(xptr, afp_list, afp_link, xtmp)
			TAILQ_REMOVE(afp_list, xptr, afp_link);
	}
}

int
get_append_list(struct xattr_list *xlist,
		struct xattr_list *append_list, const char *attr)
{
	struct xattr *xptr = NULL, *xtmp = NULL;

	if (xlist == NULL || append_list == NULL)
		return (-1);

	TAILQ_FOREACH_REVERSE_SAFE(xptr, xlist, xattr_list, link, xtmp) {
		if (attr == NULL) {
			TAILQ_INSERT_HEAD(append_list, xptr, append_link);

		} else if (strcmp(xptr->name, attr) == 0) {
			TAILQ_INSERT_HEAD(append_list, xptr, append_link);
			break;
		}
	}

	return (0);
}

int
fix_append_list(int fd, const char *path,
		u_int64_t flags, struct xattr_list *append_list)
{
	int ret = 0, setret = 0;
	struct xattr *xptr = NULL, *xtmp = NULL;

	if (append_list == NULL)
		return (-1);

	TAILQ_FOREACH_REVERSE(xptr, append_list, xattr_list, append_link) {
		if (flags & F_DEBUG) {
			printf("%s: %02x %02x %02x / %02x %02x %02x [%ld]\n", path,
				(unsigned char)xptr->value[0],
				(unsigned char)xptr->value[1],
				(unsigned char)xptr->value[2],
				(unsigned char)xptr->value[xptr->length - 2],
				(unsigned char)xptr->value[xptr->length - 1],
				(unsigned char)xptr->value[xptr->length],
				xptr->length);
		}

		if (flags & F_APPEND_NULL) {
			if ((flags & F_DRY_RUN) == 0) {
				char *buf = NULL;
				int length = 0;

				length = xptr->length + 1;
				if ((buf = malloc(length)) == NULL) {
					warn("malloc");
					return (-1);
				}

				memcpy(buf, xptr->value, xptr->length);
				buf[length] = '\0';

				free(xptr->value);
				xptr->value = buf;
				xptr->length = length;

				if ((setret = extattr_set_fd(fd, EXTATTR_NAMESPACE_USER,
					xptr->name, xptr->value, xptr->length)) < 0) {
					warn("extattr_set_fd");
					ret |= EX_EA_CORRUPTED;
				} 
			}

			if (setret > 0 || flags & F_DRY_RUN) {
				ret |= EX_OK;
				if (flags & F_VERBOSE)
					printf("%s: %s null byte appended\n", path, xptr->name);
			}
		}
	}

	return (ret);
}

void
unlink_append_list(struct xattr_list *append_list)
{
	if (append_list != NULL) {
		struct xattr *xptr = NULL, *xtmp = NULL;

		TAILQ_FOREACH_SAFE(xptr, append_list, append_link, xtmp)
			TAILQ_REMOVE(append_list, xptr, append_link);
	}
}

void
free_extended_attributes(struct xattr_list *xlist)
{
	if (xlist != NULL) {
		struct xattr *xptr = NULL, *xtmp = NULL;

		TAILQ_FOREACH_SAFE(xptr, xlist, link, xtmp) {
			TAILQ_REMOVE(xlist, xptr, link);
			free(xptr->name);
			free(xptr->value);
			free(xptr);
		}
	}
}

int
main(int argc, char **argv)
{
	int fd, ch, setret, ret = 0;
	char *prog, *path, *rp, *attr;
	struct xattr *xptr, *xtmp;
	struct xattr_list xlist, afp_list, append_list;
	u_int64_t flags = F_NONE;

	prog = path = rp = attr = NULL;

	prog = basename(argv[0]);
	if (argc < 2)
		usage(prog);

	while ((ch = getopt(argc, argv, "acCdfn:v")) != -1) {
		switch (ch) {
			case 'a':
				flags |= (F_APPEND_NULL_ALL | F_APPEND_NULL);
				if (attr != NULL) {
					free(attr);
					attr = NULL;
				}
				break;
			case 'c':
				flags |= F_CHECK_AFP_EA;
				flags &= ~F_FIX_AFP_EA;
				break;
			case 'C':
				flags |= F_DRY_RUN;
				break;
			case 'd':
				flags |= F_DEBUG;
				break;
			case 'f':
				flags |= F_FIX_AFP_EA;
				flags &= ~F_CHECK_AFP_EA;
				break;
			case 'n':
				attr = strdup(optarg);
				flags |= F_APPEND_NULL;
				flags &= ~F_APPEND_NULL_ALL;
				break;
			case 'v':
				flags |= F_VERBOSE;
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
			pathbuf[nread - 1] = '\0';
			path = &pathbuf[0];
		}
	}

	if (path == NULL && ((path = argv[0]) == NULL)) {
		free(attr);
		usage(prog);
	}

	if ((rp = realpath(path, NULL)) == NULL) {
		free(attr);
		err(EX_OSERR, "%s", path);
	}

	if (access(rp, F_OK) != 0) {
		free(rp);
		free(attr);
		err(EX_OSERR, "%s", path);
	}

	if ((fd = open(rp, O_RDONLY)) < 0) {
		free(rp);
		warnc(EX_OSERR, "%s", path);
		return (-1);
	}

	TAILQ_INIT(&xlist);
	TAILQ_INIT(&afp_list);
	TAILQ_INIT(&append_list);

#define cleanup() \
	unlink_afp_list(&afp_list); \
	unlink_append_list(&append_list); \
	free_extended_attributes(&xlist); \
	free(attr); \
	free(rp); \
	close(fd);

	if (get_extended_attributes(fd, &xlist) < 0) {
		ret = EX_DATAERR;
		cleanup();
		return ret;
	}

	if (flags & F_CHECK_AFP_EA || flags & F_FIX_AFP_EA) {
		get_afp_list(&xlist, &afp_list);
		if ((setret = fix_afp_list(fd, path, flags, &afp_list)) < 0) {
			ret = EX_DATAERR;
			cleanup();
			return ret;
		}
		ret = setret;
	}

	if (flags & F_APPEND_NULL_ALL || flags & F_APPEND_NULL) {
		get_append_list(&xlist, &append_list, attr);
		if ((setret = fix_append_list(fd, path, flags, &append_list)) < 0) {
			ret = EX_DATAERR;
			cleanup();
			return ret;
		}
		ret = setret;
	}

	cleanup();
	return (ret);

#undef cleanup
}
