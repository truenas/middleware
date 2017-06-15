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
#include <string.h>
#include <stdlib.h>
#include <sysexits.h>
#include <unistd.h>

struct windows_acl_info {

#define	WA_NULL			0x00000000	/* nothing */
#define	WA_FILES		0x00000001	/* only files */
#define	WA_DIRECTORIES	0x00000002	/* only directories */
#define	WA_APPEND		0x00000004	/* append entrie(s) */
#define	WA_REMOVE		0x00000008	/* remove entrie(s) */
#define	WA_UPDATE		0x00000010	/* update entrie(s) */
#define	WA_RECURSIVE	0x00000020	/* recursive */
#define	WA_VERBOSE		0x00000040	/* print more stuff */
#define	WA_RESET		0x00000080	/* set defaults */
#define WA_DOSATTRIB	0x00000100	/* DOS extended attribute */

/* default ACL entries if none are specified */
#define	WA_ENTRY_OWNER		"owner@:rwxpDdaARWcCos:fd:allow"
#define	WA_ENTRY_GROUP		"group@:rwxpDdaARWcCos:fd:allow"
#define	WA_ENTRY_EVERYONE	"everyone@:rxaRc:fd:allow"

#define	WA_OP_SET	(WA_APPEND|WA_REMOVE|WA_UPDATE|WA_RESET)
#define	WA_OP_CHECK(flags, bit) ((flags & ~bit) & WA_OP_SET)

	char *owner_entry;
	char *group_entry;
	char *everyone_entry;
	char *path;
	acl_t dacl;
	acl_t facl;
	uid_t uid;
	gid_t gid;
	int	flags;
	int index;
};


struct {
	const char *str;
	int action;
} actions[] = {
	{	"append",	WA_APPEND	},
	{	"update",	WA_UPDATE	},
	{	"remove",	WA_REMOVE	},
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

	w->owner_entry = NULL;
	w->group_entry = NULL;
	w->everyone_entry = NULL;
	w->path = NULL;
	w->dacl = NULL;
	w->facl = NULL;
	w->uid = -1;
	w->gid = -1;
	w->flags = 0;
	w->index = -1;

	return (w);
}


static void
free_windows_acl_info(struct windows_acl_info *w)
{
	if (w == NULL)
		return;

	free(w->owner_entry);
	free(w->group_entry);
	free(w->everyone_entry);
	free(w->path);
	acl_free(w->dacl);
	acl_free(w->facl);
	free(w);
}


static void
usage(char *path)
{
	fprintf(stderr,
		"Usage: %s [OPTIONS] ...\n"
		"Where option is:\n"
		"    -a <add|update|remove|reset> # action to perform\n"
		"    -o <owner permission>        # owner ACL entry\n"
		"    -g <group permission>        # group ACL entry\n"
		"    -e <everyone permission>     # everyone ACL entry\n"
		"    -O <owner>                   # change owner\n"
		"    -G <group>                   # change group\n"
		"    -p <path>                    # path to set\n"
		"    -i <index>                   # Index\n"
		"    -f                           # only set files\n"
		"    -d                           # only set directories\n"
		"    -r                           # recursive\n"
		"    -v                           # verbose\n"
		"    -x                           # remove DOSATTRIB EA\n",
		path
	);

	exit(0);
}

/* merge two acl entries together */
static int
merge_acl_entries(acl_entry_t *entry1, acl_entry_t *entry2)
{
	acl_permset_t permset;
	acl_entry_type_t entry_type;
	acl_flagset_t flagset;

	if (acl_get_permset(*entry1, &permset) < 0)
		err(EX_OSERR, "acl_get_permset() failed");
	if (acl_set_permset(*entry2, permset) < 0)
		err(EX_OSERR, "acl_set_permset() failed");
	if (acl_get_entry_type_np(*entry1, &entry_type) < 0)
		err(EX_OSERR, "acl_get_entry_type_np() failed");
	if (acl_set_entry_type_np(*entry2, entry_type) < 0)
		err(EX_OSERR, "acl_set_entry_type_np() failed");
	if (acl_get_flagset_np(*entry1, &flagset) < 0)
		err(EX_OSERR, "acl_get_flagset_np() failed");
	if (acl_set_flagset_np(*entry2, flagset) < 0)
		err(EX_OSERR, "acl_set_flagset_np() failed");

	return (0);
}


/* merge two acl entries together if the qualifier is the same */
static int
merge_user_group(acl_entry_t *entry1, acl_entry_t *entry2)
{
	acl_permset_t permset;
	acl_entry_type_t entry_type;
	acl_flagset_t flagset;
	uid_t *id1, *id2;
	int rval = 0;

	if ((id1 = acl_get_qualifier(*entry1)) == NULL)
		err(EX_OSERR, "acl_get_qualifier() failed");
	if ((id2 = acl_get_qualifier(*entry2)) == NULL)
		err(EX_OSERR, "acl_get_qualifier() failed");
	if (*id1 == *id2) {
		merge_acl_entries(entry1, entry2);
		rval = 1;
	}

	acl_free(id1);
	acl_free(id2);

	return (rval);
}

/* merge 2 acl's together */
static int
merge_acl(acl_t acl, acl_t *prev_acl, const char *path)
{
	acl_t acl_new;
	acl_permset_t permset;
	acl_flagset_t flagset;
	acl_tag_t tag, tag_new;
	acl_entry_t entry, entry_new;
	acl_entry_type_t entry_type, entry_type_new;
	int entry_id, entry_id_new, have_entry, had_entry, entry_number = 0;

	if ((acl_new = acl_dup(*prev_acl)) == NULL)
		err(EX_OSERR, "%s: acl_dup() failed", path);

	entry_id = ACL_FIRST_ENTRY;
	while (acl_get_entry(acl, entry_id, &entry) == 1) {
		entry_id = ACL_NEXT_ENTRY;
		have_entry = had_entry = 0;

		entry_id_new = ACL_FIRST_ENTRY;
		while (acl_get_entry(acl_new, entry_id_new, &entry_new) > 0) {
			entry_id_new = ACL_NEXT_ENTRY;

			if (acl_get_tag_type(entry, &tag) < 0)
				err(EX_OSERR, "%s: acl_get_tag_type() failed", path);
			if (acl_get_tag_type(entry_new, &tag_new) < 0)
				err(EX_OSERR, "%s: acl_get_tag_type() failed", path);
			if (tag != tag_new)
				continue;

			if (acl_get_entry_type_np(entry, &entry_type) < 0)
				err(EX_OSERR, "%s: acl_get_entry_type_np() failed", path);
			if (acl_get_entry_type_np(entry_new, &entry_type_new) < 0)
				err(EX_OSERR, "%s: acl_get_entry_type_np() failed", path);
			if (entry_type != entry_type_new)
				continue;
		
			switch(tag) {
				case ACL_USER:
				case ACL_GROUP:
					have_entry = merge_user_group(&entry, &entry_new);
					if (have_entry == 0)
						break;

				case ACL_USER_OBJ:
				case ACL_GROUP_OBJ:
				case ACL_EVERYONE:
					merge_acl_entries(&entry, &entry_new);
					had_entry = have_entry = 1;
					break;

				default:
					errx(EX_OSERR, "%s: invalid tag type: %i", path, tag);
					break;
			}
		}

		if (had_entry == 0) {
			if (acl_create_entry_np(&acl_new, &entry_new, entry_number) < 0) {
				warn("%s: acl_create_entry_np() failed", path); 
				acl_free(acl_new);
				return (-1);
			}

			entry_number++;
			if (acl_copy_entry(entry_new, entry) < 0)
				err(EX_OSERR, "%s: acl_copy_entry() failed", path);
		}
	}

	acl_free(*prev_acl);
	*prev_acl = acl_new;

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

		acl_delete_flag_np(acl_flags, ACL_ENTRY_FILE_INHERIT);
		acl_delete_flag_np(acl_flags, ACL_ENTRY_DIRECTORY_INHERIT);
		acl_delete_flag_np(acl_flags, ACL_ENTRY_NO_PROPAGATE_INHERIT);
		acl_delete_flag_np(acl_flags, ACL_ENTRY_INHERIT_ONLY);

		if (acl_set_flagset_np(acl_entry, acl_flags) < 0)
			err(EX_OSERR, "acl_set_flagset_np() failed");
	}

	return (0);
}


/* update an existing ACL */
static int
windows_acl_update(struct windows_acl_info *w, const char *path)
{
	struct stat st;
	acl_t acl, acl_new;

	if ((acl = acl_get_file(path, ACL_TYPE_NFS4)) == NULL)
		err(EX_OSERR, "%s: acl_get_filed() failed", path);

	bzero(&st, sizeof(st));
	if (stat(path, &st) < 0)
		err(EX_OSERR, "%s: acl_from_text() failed", path);

	acl_new = (S_ISDIR(st.st_mode) == 0) ? w->facl : w->dacl;

	/* merge the new acl with the existing acl */
	if (merge_acl(acl_new, &acl, path) < 0)
		warn("%s: merge_acl() failed", path);

	/* write out the acl to the file */
	if (acl_set_file(path, ACL_TYPE_NFS4, acl) < 0)
		warn("%s: acl_set_file() failed", path);
	acl_free(acl);

	return (0);
}


/* append an ACL */
static int
windows_acl_append(struct windows_acl_info *w, const char *path)
{
	struct stat st;
	acl_t acl, acl_new;

	if ((acl = acl_get_file(path, ACL_TYPE_NFS4)) == NULL)
		err(EX_OSERR, "%s: acl_get_filed() failed", path);

	bzero(&st, sizeof(st));
	if (stat(path, &st) < 0)
		err(EX_OSERR, "%s: acl_from_text() failed", path);

	acl_new = (S_ISDIR(st.st_mode) == 0) ? w->facl : w->dacl;

	/* merge the new acl with the existing acl */
	if (merge_acl(acl_new, &acl, path) < 0)
		warn("%s: merge_acl() failed", path);

	/* write out the acl to the file */
	if (acl_set_file(path, ACL_TYPE_NFS4, acl) < 0)
		warn("%s: acl_set_file() failed", path);
	acl_free(acl);

	return (0);
}


/* remove an ACL */
static int
windows_acl_remove(struct windows_acl_info *w, const char *path)
{
	acl_t acl;

	if ((acl = acl_get_file(path, ACL_TYPE_NFS4)) == NULL)
		err(EX_OSERR, "%s: acl_get_filed() failed", path);

	/* remove the entry by index */
    if (acl_delete_entry_np(acl, w->index) < 0)
		err(EX_OSERR, "%s: acl_delete_entry() failed", path);

	/* write out the acl to the file */
	if (acl_set_file(path, ACL_TYPE_NFS4, acl) < 0)
		warn("%s: acl_set_file() failed", path);

	acl_free(acl);
	return (0);
}


/* reset an ACL */
static int
windows_acl_reset(struct windows_acl_info *w, const char *path)
{
	char *buf;
	struct stat st;
	acl_t acl, acl_new, tmp;

	if ((acl = acl_get_file(path, ACL_TYPE_NFS4)) == NULL)
		err(EX_OSERR, "%s: acl_get_filed() failed", path);

	/* remove extended entries */
	if ((tmp = acl_strip_np(acl, 0)) == NULL)
		err(EX_OSERR, "%s: acl_strip_np() failed", path);

	acl_free(acl);
	acl = tmp;

	bzero(&st, sizeof(st));
	if (stat(path, &st) < 0)
		err(EX_OSERR, "%s: acl_from_text() failed", path);

	acl_new = (S_ISDIR(st.st_mode) == 0) ? w->facl : w->dacl;

	/* merge the new acl with the existing acl */
	if (merge_acl(acl_new, &acl, path) < 0)
		warn("%s: merge_acl() failed", path);
	acl_free(acl);

	/* write out the acl to the file */
	if (acl_set_file(path, ACL_TYPE_NFS4, acl_new) < 0)
		warn("%s: acl_set_file() failed", path);

	return (0);
}


static void
clear_dosattrib(struct windows_acl_info *w, const char *path)
{
	if (extattr_get_file(path, EXTATTR_NAMESPACE_USER,
		"DOSATTRIB", NULL, 0) > 0) {
		if (extattr_delete_file(path,
			EXTATTR_NAMESPACE_USER, "DOSATTRIB") < 0) 
			warn("%s: extattr_delete_file() failed", path);
	}
}


static int
set_windows_acl(struct windows_acl_info *w, FTSENT *fts_entry)
{
	char *path;

	if (fts_entry == NULL) 
		path = w->path;
	else
		path = fts_entry->fts_accpath;

	if (w->flags & WA_VERBOSE)
		fprintf(stdout, "%s\n", path);

	if (w->flags & WA_UPDATE)
		windows_acl_update(w, path);
	else if (w->flags & WA_APPEND)
		windows_acl_append(w, path);
	else if (w->flags & WA_REMOVE)
		windows_acl_remove(w, path);
	else if (w->flags & WA_RESET)
		windows_acl_reset(w, path);

	if (w->flags & WA_DOSATTRIB)
		clear_dosattrib(w, path);

	if (w->uid != -1 || w->gid != -1) {
		if (chown(path, w->uid, w->gid) < 0)
			warn("%s: chown() failed", path);
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

	/* recursive not set, only do this entry */
	if (!(w->flags & WA_RECURSIVE)) {
		set_windows_acl(w, NULL);
		return (0);
	}

	paths[0] = w->path;
	paths[1] = NULL;
	options = FTS_LOGICAL|FTS_NOSTAT;

	if ((tree = fts_open(paths, options, fts_compare)) == NULL)
		err(EX_OSERR, "fts_open");

	/* traverse directory hierarchy */
	for (rval = 0; (entry = fts_read(tree)) != NULL;) {
		switch (entry->fts_info) {
			case FTS_D:
				if (w->flags & WA_DIRECTORIES)
					set_windows_acl(w, entry);
				break;	

			case FTS_F:
				if (w->flags & WA_FILES)
					set_windows_acl(w, entry);
				break;	

			case FTS_ERR:
				warnx("%s: %s", entry->fts_path, strerror(entry->fts_errno));
				rval = -2;
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

	if (w->flags & WA_REMOVE) {
		if (w->index < 0)
			errx(EX_USAGE, "remove specified without index");

	} else if (WA_OP_CHECK(w->flags, ~WA_OP_SET) &&
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

	/* set defaults if none specified */
	if (w->flags & WA_RESET) {
		if (w->owner_entry == NULL)
			setarg(&w->owner_entry, WA_ENTRY_OWNER);
		if (w->group_entry == NULL)
			setarg(&w->group_entry, WA_ENTRY_GROUP);
		if (w->everyone_entry == NULL)
			setarg(&w->everyone_entry, WA_ENTRY_EVERYONE);
	}

	/* create an acl string */
	ptr = &buf[0];
	if (w->owner_entry != NULL)
		copyarg(&ptr, w->owner_entry);
	if (w->group_entry != NULL)
		copyarg(&ptr, w->group_entry);
	if (w->everyone_entry != NULL)
		copyarg(&ptr, w->everyone_entry);

	/* turn our acl string into an acl */
	if ((acl = acl_from_text(buf)) == NULL)
		err(EX_OSERR, "acl_from_text() failed");

	/* create a directory acl */
	if (w->flags & WA_DIRECTORIES) {
		if ((w->dacl = acl_dup(acl)) == NULL)
			err(EX_OSERR, "acl_dup() failed");
	}

	/* create a file acl */
	if (w->flags & WA_FILES) {
		if ((w->facl = acl_dup(acl)) == NULL)
			err(EX_OSERR, "acl_dup() failed");
		remove_inherit_flags(&w->facl);
	}

	acl_free(acl);
}


int
main(int argc, char **argv)
{
	int ch;
	struct windows_acl_info *w;

	if (argc < 2)
		usage(argv[0]);

	w = new_windows_acl_info();
	w->flags = (WA_FILES|WA_DIRECTORIES);

	while ((ch = getopt(argc, argv, "a:o:g:e:O:G:p:i:fdrvx")) != -1) {
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

			case 'o':
				setarg(&w->owner_entry, optarg);
				break;

			case 'g':
				setarg(&w->group_entry, optarg);
				break;

			case 'e':
				setarg(&w->everyone_entry, optarg);
				break;

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

			case 'p':
				setarg(&w->path, optarg);
				break;

			case 'i':
				w->index = strtol(optarg, NULL, 10);
				break;

			case 'f':
				w->flags &= ~WA_DIRECTORIES;
				break;

			case 'd':
				w->flags &= ~WA_FILES;
				break;

			case 'r':
				w->flags |= WA_RECURSIVE;
				break;

			case 'v':
				w->flags |= WA_VERBOSE;
				break;

			case 'x':
				w->flags |= WA_DOSATTRIB;
				break;

			case '?':
			default:
				usage(argv[0]);
		}
	}

	make_acls(w);
	usage_check(w);
	set_windows_acls(w);

	free_windows_acl_info(w);
	return (0);
}
