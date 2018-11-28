/*-
 * Copyright 2014 iXsystems, Inc.
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
#include <sys/acl.h>
#include <sys/extattr.h>
#include <sys/stat.h>
#include <err.h>
#include <fts.h>
#include <grp.h>
#include <pwd.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <stdlib.h>
#include <sysexits.h>
#include <unistd.h>

struct windows_acl_info {

#define	WA_NULL			0x00000000	/* nothing */
#define	WA_RECURSIVE		0x00000001	/* recursive */
#define	WA_VERBOSE		0x00000002	/* print more stuff */
#define	WA_RESET		0x00000004	/* set defaults */
#define	WA_CLONE		0x00000008	/* clone an ACL */
#define	WA_TRAVERSE		0x00000010	/* traverse filesystem mountpoints */
#define	WA_PHYSICAL		0x00000020	/* do not follow symlinks */

/* default ACL entries if none are specified */
#define	WA_DEFAULT_ACL		"owner@:rwxpDdaARWcCos:fd:allow,group@:rwxpDdaARWcCos:fd:allow,everyone@:rxaRc:fd:allow"

#define	WA_OP_SET	(WA_CLONE|WA_RESET)
#define	WA_OP_CHECK(flags, bit) ((flags & ~bit) & WA_OP_SET)

	char *source;
	char *path;
	acl_t source_acl;
	acl_t dacl;
	acl_t facl;
	uid_t uid;
	gid_t gid;
	int	flags;
};


struct {
	const char *str;
	int action;
} actions[] = {
	{	"clone",	WA_CLONE	},
	{	"reset",	WA_RESET	}
};


size_t actions_size = sizeof(actions) / sizeof(actions[0]);


static void
setarg(char **pptr, const char *src)
{
	char *ptr;

	ptr = *pptr;
	if (ptr != NULL)
		free(ptr);
	ptr = strdup(src);
	if (ptr == NULL)
		err(EX_OSERR, NULL);

	*pptr = ptr;
}


static void
copyarg(char **pptr, const char *src)
{
	int len;
	char *ptr;

	if (pptr == NULL)
		err(EX_USAGE, "NULL destination");
	if (src == NULL)
		err(EX_USAGE, "NULL source");

	ptr = *pptr;
	len = strlen(src);
	strncpy(ptr, src, len);
	ptr += len;
	*ptr = '\n';
	ptr++;
	*ptr = 0;

	*pptr = ptr;
}


static int
get_action(const char *str)
{
	int i;
	int action = WA_NULL;

	for (i = 0;i < actions_size;i++) {
		if (strcasecmp(actions[i].str, str) == 0) {
			action = actions[i].action;
			break;
		}
	}

	return action;
}


static struct windows_acl_info *
new_windows_acl_info(void)
{
	struct windows_acl_info *w;

	if ((w = malloc(sizeof(*w))) == NULL)
		err(EX_OSERR, "malloc() failed");

	w->source = NULL;
	w->path = NULL;
	w->source_acl = NULL;
	w->dacl = NULL;
	w->facl = NULL;
	w->uid = -1;
	w->gid = -1;
	w->flags = 0;

	return (w);
}


static void
free_windows_acl_info(struct windows_acl_info *w)
{
	if (w == NULL)
		return;

	free(w->source);
	free(w->path);
	acl_free(w->source_acl);
	acl_free(w->dacl);
	acl_free(w->facl);
	free(w);
}


static void
usage(char *path)
{
	if (strcmp(path, "cloneacl") == 0) {
	fprintf(stderr,
		"Usage: %s [OPTIONS] ...\n"
		"Where option is:\n"
		"    -s <path>                    # source for ACL. If none specified then ACL taken from -p\n"
		"    -p <path>                    # path to recursively set ACL\n"
		"    -v                           # verbose\n",
		path
	);
	} else {
	fprintf(stderr,
		"Usage: %s [OPTIONS] ...\n"
		"Where option is:\n"
		"    -a <clone|reset> 		# action to perform\n"
		"    -O <owner>                	# change owner\n"
		"    -G <group>                	# change group\n"
		"    -s <source>         	# source (if cloning ACL). If none specified then ACL taken from -p\n"
		"    -p <path>                 	# path to set\n"
		"    -l                        	# do not traverse symlinks\n"
		"    -r                        	# recursive\n"
		"    -v                        	# verbose\n"
		"    -x                        	# traverse filesystem mountpoints\n",
		path
	);
	}

	exit(0);
}

/* add inherited flag to ACES in ACL */
static int
set_inherited_flag(acl_t *acl)
{
        int entry_id;
        acl_entry_t acl_entry;
        acl_flagset_t acl_flags;
                 
        entry_id = ACL_FIRST_ENTRY;
        while (acl_get_entry(*acl, entry_id, &acl_entry) > 0) {
                entry_id = ACL_NEXT_ENTRY;

                if (acl_get_flagset_np(acl_entry, &acl_flags) < 0)
                        err(EX_OSERR, "acl_get_flagset_np() failed");
                if ((*acl_flags & ACL_ENTRY_INHERITED) == 0) {
                    acl_add_flag_np(acl_flags, ACL_ENTRY_INHERITED);

                    if (acl_set_flagset_np(acl_entry, acl_flags) < 0)
                            err(EX_OSERR, "acl_set_flagset_np() failed");
                }
        }

        return (0);
}

/* only directories can have inherit flags set */
static int
remove_inherit_flags(acl_t *acl)
{
	int entry_id;
	acl_entry_t acl_entry;
	acl_flagset_t acl_flags;

	entry_id = ACL_FIRST_ENTRY;
	while (acl_get_entry(*acl, entry_id, &acl_entry) > 0) {
		entry_id = ACL_NEXT_ENTRY;

		if (acl_get_flagset_np(acl_entry, &acl_flags) < 0)
			err(EX_OSERR, "acl_get_flagset_np() failed");
		if (*acl_flags & (ACL_ENTRY_FILE_INHERIT|ACL_ENTRY_DIRECTORY_INHERIT|
				  ACL_ENTRY_NO_PROPAGATE_INHERIT|ACL_ENTRY_INHERIT_ONLY)) {
			acl_delete_flag_np(acl_flags, (
				ACL_ENTRY_FILE_INHERIT|ACL_ENTRY_DIRECTORY_INHERIT|
				ACL_ENTRY_NO_PROPAGATE_INHERIT|ACL_ENTRY_INHERIT_ONLY
				));

			if (acl_set_flagset_np(acl_entry, acl_flags) < 0)
				err(EX_OSERR, "acl_set_flagset_np() failed");

		}
	}

	return (0);
}

static int
set_windows_acl(struct windows_acl_info *w, FTSENT *fts_entry)
{
	char *path;
	char *buf;
	acl_t acl_new;
	if (fts_entry == NULL) 
		path = w->path;
	else
		path = fts_entry->fts_accpath;

	if (w->flags & WA_VERBOSE)
		fprintf(stdout, "%s\n", path);

	/* don't set inherited flag on root dir. This is required for zfsacl:map_dacl_protected */
        if (fts_entry->fts_level == FTS_ROOTLEVEL) {
                acl_new = w->source_acl;
        }
        else {
                acl_new = ((fts_entry->fts_statp->st_mode & S_IFDIR) == 0) ? w->facl : w->dacl;
        }

	/* write out the acl to the file */

	if (acl_set_file(path, ACL_TYPE_NFS4, acl_new) < 0) {
		warn("%s: acl_set_file() failed", path);
		return (-1);
	}

	if (w->uid != -1 || w->gid != -1) {
		if (chown(path, w->uid, w->gid) < 0) {
			warn("%s: chown() failed", path);
			return (-1);
		}
	}

 
	return (0);
}


static int
fts_compare(const FTSENT * const *s1, const FTSENT * const *s2)
{
	return (strcoll((*s1)->fts_name, (*s2)->fts_name));
}


static int
set_windows_acls(struct windows_acl_info *w)
{
	FTS *tree;
	FTSENT *entry;
	int options = 0;
	char *paths[4];
	int rval;

	if (w == NULL)
		return (-1);

	paths[0] = w->path;
	paths[1] = NULL;

	if ((w->flags & WA_TRAVERSE) == 0 ) {
		options |= FTS_XDEV;
	}
	if ((w->flags & WA_PHYSICAL) == 0) {
		options |= FTS_LOGICAL;	
	}

	if ((tree = fts_open(paths, options, fts_compare)) == NULL)
		err(EX_OSERR, "fts_open");

	/* traverse directory hierarchy */
	for (rval = 0; (entry = fts_read(tree)) != NULL;) {
		if ((w->flags & WA_RECURSIVE) == 0) {
			if (entry->fts_level == FTS_ROOTLEVEL){
				rval = set_windows_acl(w, entry);
				break;
			}
		}

		switch (entry->fts_info) {
			case FTS_D:
				rval = set_windows_acl(w, entry);
				break;	

			case FTS_F:
				rval = set_windows_acl(w, entry);
				break;	

			case FTS_ERR:
				warnx("%s: %s", entry->fts_path, strerror(entry->fts_errno));
				rval = -2;
				continue;
		}
		if (rval < 0) {
			err(EX_OSERR, "%s: set_windows_acl() failed", entry->fts_accpath);
			continue;
		}

	} 

	return (rval);
}


static void
usage_check(struct windows_acl_info *w)
{
	if (w->path == NULL)
		errx(EX_USAGE, "no path specified");

	if (!WA_OP_CHECK(w->flags, ~WA_OP_SET) &&
		w->dacl == NULL && w->facl == NULL)
		errx(EX_USAGE, "nothing to do");

	if (WA_OP_CHECK(w->flags, ~WA_OP_SET) &&
		w->dacl == NULL && w->facl == NULL && !(w->flags & WA_RESET)) {
		errx(EX_USAGE, "no entries specified and not resetting");
	}
}


/* create directory and file ACL's */
static void
make_acls(struct windows_acl_info *w)
{
	char *ptr;
	char buf[8192];
	acl_t acl;
	char *default_acl = WA_DEFAULT_ACL;

	/* create an acl string */
	ptr = &buf[0];
	copyarg(&ptr, default_acl);

	/* turn our acl string into an acl */
	if ((acl = acl_from_text(buf)) == NULL)
		err(EX_OSERR, "acl_from_text() failed");

	/* set the source ACL for top level directory */
	if ((w->source_acl = acl_dup(acl)) == NULL) {
		err(EX_OSERR, "acl_dup() failed");
	}

	/* create a directory acl */
	if ((w->dacl = acl_dup(acl)) == NULL)
		err(EX_OSERR, "acl_dup() failed");
	set_inherited_flag(&w->dacl);	

	/* create a file acl */
	if ((w->facl = acl_dup(acl)) == NULL)
		err(EX_OSERR, "acl_dup() failed");
	remove_inherit_flags(&w->facl);
	set_inherited_flag(&w->facl);	

	acl_free(acl);
}

static void
clone_acls(struct windows_acl_info *w)
{
	/* create a directory acl */
	if ((w->dacl = acl_dup(w->source_acl)) == NULL)
		err(EX_OSERR, "acl_dup() failed");

	set_inherited_flag(&w->dacl);

	/* create a file acl */
	if ((w->facl = acl_dup(w->source_acl)) == NULL)
		err(EX_OSERR, "acl_dup() failed");
	remove_inherit_flags(&w->facl);
	set_inherited_flag(&w->facl);
}

int
main(int argc, char **argv)
{
	int 	ch, ret;
	struct 	windows_acl_info *w;
	acl_t	source_acl;
	char *p = argv[0];

	if (argc < 2)
		usage(argv[0]);

	w = new_windows_acl_info();

	if (strcmp(p, "cloneacl") == 0) {
		w->flags |= WA_CLONE;
		w->flags |= WA_RECURSIVE;
		while ((ch = getopt(argc, argv, "s:p:v")) != -1) {
			switch(ch) {
			case 's':
				setarg(&w->source, optarg);
				break;
			case 'p':
				setarg(&w->path, optarg);
				break;
			case 'v':
				w->flags |= WA_VERBOSE;
				break;
			case '?':
			default:
				usage(argv[0]);
			}
		}
	} else {
		while ((ch = getopt(argc, argv, "a:O:G:s:p:lrvx")) != -1) {
			switch (ch) {
				case 'a': {
					int action = get_action(optarg);
					if (action == WA_NULL)
						errx(EX_USAGE, "invalid action");
					if (WA_OP_CHECK(w->flags, action))
						errx(EX_USAGE, "only one action can be specified");
					w->flags |= action;
					break;
				}

				case 'O': {
					struct passwd *p = getpwnam(optarg);
					if (p == NULL)
						errx(EX_OSERR, "getpwnam() failed");
					w->uid = p->pw_uid;
					break;
				}

				case 'G': {
					struct group *g = getgrnam(optarg);
					if (g == NULL)
						errx(EX_OSERR, "getgrnam() failed");
					w->gid = g->gr_gid;
					break;
				}

				case 's':
					setarg(&w->source, optarg);
					break;

				case 'l':
					w->flags |= WA_PHYSICAL;
					break;

				case 'p':
					setarg(&w->path, optarg);
					break;

				case 'r':
					w->flags |= WA_RECURSIVE;
					break;

				case 'v':
					w->flags |= WA_VERBOSE;
					break;

				case 'x':
					w->flags |= WA_TRAVERSE;
					break;

				case '?':
				default:
					usage(argv[0]);
			}
		}
	}

	/* set the source to the destination if we lack -s */
	if (w->source == NULL) {
		w->source = w->path;
	}

	if (pathconf(w->source, _PC_ACL_NFS4) < 0) {
		warn("%s: pathconf(..., _PC_ACL_NFS4) failed. Path does not support NFS4 ACL.", w->source);
		free_windows_acl_info(w);
		return (1);
	}

	if (w->flags & WA_CLONE){
		source_acl = acl_get_file(w->source, ACL_TYPE_NFS4);

		if (source_acl == NULL) {
			err(EX_OSERR, "%s: acl_get_file() failed", w->source);
			free_windows_acl_info(w);
			return (1);
		}

		w->source_acl = acl_dup(source_acl);
		acl_free(source_acl);
		clone_acls(w);
	} else {
		make_acls(w);
	}

	usage_check(w);

	if (set_windows_acls(w) <0) {
		ret = 1;
	}

	free_windows_acl_info(w);
	return (ret);
}
