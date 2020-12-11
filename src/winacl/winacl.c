/*-
 * Copyright 2020 iXsystems, Inc.
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
#include <errno.h>
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


#define	WA_NULL			0x00000000	/* nothing */
#define	WA_RECURSIVE		0x00000001	/* recursive */
#define	WA_VERBOSE		0x00000002	/* print more stuff */
#define	WA_CLONE		0x00000008	/* clone an ACL */
#define	WA_TRAVERSE		0x00000010	/* traverse filesystem mountpoints */
#define	WA_PHYSICAL		0x00000020	/* do not follow symlinks */
#define	WA_STRIP		0x00000040	/* strip ACL */
#define	WA_CHOWN		0x00000080	/* only chown */
#define	WA_TRIAL		0x00000100	/* trial run */
#define	WA_RESTORE		0x00000200	/* restore ACL */
#define	WA_FORCE		0x00000400	/* force */

#define	WA_OP_SET	(WA_CLONE|WA_STRIP|WA_CHOWN|WA_RESTORE)
#define	WA_OP_CHECK(flags, bit) ((flags & ~bit) & WA_OP_SET)
#define	MAX_ACL_DEPTH		2

struct inherited_acls{
	acl_t dacl;
	acl_t facl;
};

struct windows_acl_info {
	char *source;
	char *path;
	char *chroot;
	acl_t source_acl;
	dev_t root_dev;
	struct inherited_acls *acls;
	uid_t uid;
	gid_t gid;
	int	flags;
};


struct {
	const char *str;
	int action;
} actions[] = {
	{	"clone",	WA_CLONE	},
	{	"strip",	WA_STRIP	},
	{	"chown",	WA_CHOWN	},
	{	"restore",	WA_RESTORE	}
};

size_t actions_size = sizeof(actions) / sizeof(actions[0]);

static int calculate_inherited_acl(struct windows_acl_info *w, acl_t parent_acl, int level);

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
	struct windows_acl_info *w = NULL;
	int i;

	w = calloc(1, sizeof(*w));
	if (w == NULL) {
		err(EX_OSERR, "calloc() failed");
	}

	w->acls = calloc(MAX_ACL_DEPTH, sizeof(struct inherited_acls));
	if (w->acls == NULL) {
		err(EX_OSERR, "calloc() failed");
	}

	for (i=0; i<=MAX_ACL_DEPTH; i++){
		w->acls[i].dacl = NULL;
		w->acls[i].facl = NULL;
	}

	w->uid = -1;
	w->gid = -1;

	return (w);
}


static void
free_windows_acl_info(struct windows_acl_info *w)
{
	if (w == NULL)
		return;
	int i;

	free(w->source);
	free(w->path);
	acl_free(w->source_acl);
	for (i=0; i<=MAX_ACL_DEPTH; i++){
		acl_free(w->acls[i].dacl);
		acl_free(w->acls[i].facl);
	}
	free(w->acls);
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
		"    -a <clone|strip|chown|restore> # action to perform <restore is experimental!>\n"
		"    -O <owner>                     # change owner\n"
		"    -G <group>                     # change group\n"
		"    -c <path>                      # chroot path\n"
		"    -s <source>                    # source (if cloning ACL). If none specified then ACL taken from -p\n"
		"    -p <path>                      # path to set\n"
		"    -r                             # recursive\n"
		"    -v                             # verbose\n"
		"    -t                             # trial run - makes no changes\n"
		"    -x                             # traverse filesystem mountpoints\n"
		"    -f                             # force acl inheritance\n",
		path
	);
	}

	exit(0);
}

static int
strip_acl(struct windows_acl_info *w, FTSENT *fts_entry)
{
	/*
	 * Convert non-trivial ACL to trivial ACL.
	 * This function is only called when action is set
	 * to 'strip'. A trivial ACL is one that is fully
	 * represented by the posix mode. If the goal is to
	 * simply remove ACLs, it will generally be more
	 * efficient to strip the ACL using setfacl -b
	 * from the root directory and then use the 'clone'
	 * action to set the ACL recursively.
	 */
	char *path;
	acl_t acl_tmp, acl_new;

	if (fts_entry == NULL)
		path = w->path;
	else
		path = fts_entry->fts_accpath;

	if (w->flags & WA_VERBOSE)
		fprintf(stdout, "%s\n", path);
	acl_tmp = acl_get_file(path, ACL_TYPE_NFS4);
	if (acl_tmp == NULL) {
		warn("%s: acl_get_file() failed", path);
		return (-1);
	}
	acl_new = acl_strip_np(acl_tmp, 0);
	if (acl_new == NULL) {
		warn("%s: acl_strip_np() failed", path);
		acl_free(acl_tmp);
		return (-1);
	}

	if (acl_set_file(path, ACL_TYPE_NFS4, acl_new) < 0) {
		warn("%s: acl_set_file() failed", path);
		acl_free(acl_tmp);
		acl_free(acl_new);
		return (-1);
	}
	acl_free(acl_tmp);
	acl_free(acl_new);

	if (w->uid != -1 || w->gid != -1) {
		if (chown(path, w->uid, w->gid) < 0) {
			warn("%s: chown() failed", path);
			return (-1);
		}
	}
	return (0);
}

static inline char *get_relative_path(FTSENT *entry, size_t plen)
{
	char *relpath = NULL;
	relpath = entry->fts_path + plen;
	if (relpath[0] == '/') {
		relpath++;
	}
	return relpath;
}

/*
 * Iterate through linked list of parent directories until we are able
 * to find one that exists in the snapshot directory. Use this ACL
 * to calculate an inherited acl.
 */
static int get_acl_parent(struct windows_acl_info *w, FTSENT *fts_entry)
{
	int rval;
	FTSENT *p = NULL;
	char *path = NULL;
	char *relpath = NULL;
	size_t plen, slen;
	char shadow_path[PATH_MAX] = {0};
	acl_t parent_acl;

	plen = strlen(w->path);
	slen = strlen(w->source);

	if (fts_entry->fts_parent == NULL) {
		/*
		 * No parent node indicates we're at fts root level.
		 */
		parent_acl = acl_get_file(w->source, ACL_TYPE_NFS4);
		if (parent_acl == NULL) {
			return -1;
		}
		rval = calculate_inherited_acl(w, parent_acl, 0);
		if (rval != 0) {
			warn("%s: acl_get_file() failed", w->source);
		}
		acl_free(parent_acl);
		return rval;
	}

	for (p=fts_entry->fts_parent; p; p=p->fts_parent) {
		rval = snprintf(shadow_path, sizeof(shadow_path),
				"%s/%s", w->source, p->fts_accpath);
		if (rval < 0) {
			warn("%s: snprintf failed", relpath);
			return -1;
		}

		parent_acl = acl_get_file(shadow_path, ACL_TYPE_NFS4);
		if (parent_acl == NULL) {
			if (errno == ENOENT) {
				continue;
			}
			else {
				warn("%s: acl_get_file() failed", shadow_path);
				return -1;

			}
		}

		rval = calculate_inherited_acl(w, parent_acl, 0);
		if (rval == 0) {
			acl_free(parent_acl);
			return 0;
		}
		warn("%s: acl_get_file() failed", shadow_path);
		acl_free(parent_acl);
	}
	return -1;
}

/*
 * Compare two acl_t structs. Return 0 on success -1 on failure.
 */
static inline int acl_cmp(acl_t source, acl_t dest, int flags)
{
	acl_entry_t s_entry, p_entry;
	acl_permset_t s_perm, p_perm;
	acl_tag_t s_tag, p_tag;
	acl_flagset_t s_flag, p_flag;

	int entry_id = ACL_FIRST_ENTRY;
	int rv;

	if (source->ats_acl.acl_cnt != dest->ats_acl.acl_cnt) {
		if (flags & WA_VERBOSE) {
			fprintf(stdout, "+ [COUNT %d -> %d] ",
				source->ats_acl.acl_cnt,
				dest->ats_acl.acl_cnt);
		}
		return -1;
	}

	while (acl_get_entry(source, entry_id, &s_entry) == 1) {
		entry_id = ACL_NEXT_ENTRY;
		rv = acl_get_entry(dest, entry_id, &p_entry);
		if (rv != 1) {
			if (flags & WA_VERBOSE) {
				fprintf(stdout, "+ [ACL_ERROR: %s] ",
					strerror(errno));
			}
			return -1;
		}

		if (s_entry->ae_tag != p_entry->ae_tag) {
			if (flags & WA_VERBOSE) {
				fprintf(stdout, "+ [ACL tag 0x%08x -> 0x%08x] ",
					s_entry->ae_tag, p_entry->ae_tag);
			}
			return -1;
		}
		if (s_entry->ae_id != p_entry->ae_id) {
			if (flags & WA_VERBOSE) {
				fprintf(stdout, "+ [ACL id %d -> %d] ",
					s_entry->ae_id, p_entry->ae_id);
			}
			return -1;
		}
		if (s_entry->ae_perm != p_entry->ae_perm) {
			if (flags & WA_VERBOSE) {
				fprintf(stdout, "+ [ACL perm 0x%08x -> 0x%08x] ",
					s_entry->ae_perm, p_entry->ae_perm);
			}
			return -1;
		}
		if (s_entry->ae_entry_type != p_entry->ae_entry_type) {
			if (flags & WA_VERBOSE) {
				fprintf(stdout, "+ [ACL entry_type 0x%08x -> 0x%08x] ",
					s_entry->ae_entry_type, p_entry->ae_entry_type);
			}
			return -1;
		}
		if (s_entry->ae_flags != p_entry->ae_flags) {
			if (flags & WA_VERBOSE) {
				fprintf(stdout, "+ [ACL entry_flags 0x%08x -> 0x%08x] ",
					s_entry->ae_flags, p_entry->ae_flags);
			}
			return -1;
		}
	}
	return 0;
}


static int
restore_acl(struct windows_acl_info *w, char *relpath, FTSENT *fts_entry, size_t slen)
{
	int rval;
	acl_t acl_new, acl_old;
	char shadow_path[PATH_MAX] = {0};

	if (strlen(relpath) + slen > PATH_MAX) {
		warn("%s: path in snapshot directory is too long", relpath);
		return -1;
	}

	rval = snprintf(shadow_path, sizeof(shadow_path), "%s/%s", w->source, relpath);
	if (rval < 0) {
		warn("%s: snprintf failed", relpath);
		return -1;
	}

	acl_new = acl_get_file(shadow_path, ACL_TYPE_NFS4);
	if (acl_new == NULL) {
		if (errno == ENOENT) {
			if (w->flags & WA_FORCE) {
				rval = get_acl_parent(w, fts_entry);
				if (rval != 0) {
					fprintf(stdout, "! %s\n", shadow_path);
					return 0;
				}
				acl_new = acl_dup(((fts_entry->fts_statp->st_mode & S_IFDIR) == 0) ? w->acls[0].facl : w->acls[0].dacl);
				if (acl_new == NULL) {
					warn("%s: acl_dup() failed", shadow_path);
					return -1;
				}
			}
			else {
				fprintf(stdout, "! %s\n", shadow_path);
				return 0;
			}
		}
		else {
			warn("%s: acl_get_file() failed", shadow_path);
			return (-1);
		}
	}

	acl_old = acl_get_file(fts_entry->fts_path, ACL_TYPE_NFS4);
	if (acl_old == NULL) {
		warn("%s: acl_get_file() failed", fts_entry->fts_path);
		return (-1);
	}

	rval = acl_cmp(acl_new, acl_old, w->flags);
	if (rval == 0) {
		return 0;
	}

	if (w->flags & WA_VERBOSE) {
		fprintf(stdout, "%s -> %s\n",
			shadow_path,
			fts_entry->fts_path);
	}
	if ((w->flags & WA_TRIAL) == 0) {
		rval = acl_set_file(fts_entry->fts_accpath,
				    ACL_TYPE_NFS4, acl_new);
		if (rval < 0) {
			warn("%s: acl_set_file() failed", fts_entry->fts_accpath);
			acl_free(acl_old);
			acl_free(acl_new);
			return -1;
		}
	}

	acl_free(acl_old);
	acl_free(acl_new);
	return 0;
}

static int
set_acl(struct windows_acl_info *w, FTSENT *fts_entry)
{
	acl_t acl_new;
	int acl_depth = 0;

	if (w->flags & WA_VERBOSE) {
		fprintf(stdout, "%s\n", fts_entry->fts_path);
	}

	/* don't set inherited flag on root dir. This is required for zfsacl:map_dacl_protected */
	if (fts_entry->fts_level == FTS_ROOTLEVEL) {
		acl_new = w->source_acl;
	}
	else {
		if ((fts_entry->fts_level -1) >= MAX_ACL_DEPTH) {
			acl_depth = MAX_ACL_DEPTH-1;
		}
		else {
			acl_depth = fts_entry->fts_level -1;
		}
		acl_new = ((fts_entry->fts_statp->st_mode & S_IFDIR) == 0) ? w->acls[acl_depth].facl : w->acls[acl_depth].dacl;
	}

	/* write out the acl to the file */
	if (acl_set_file(fts_entry->fts_accpath, ACL_TYPE_NFS4, acl_new) < 0) {
		warn("%s: acl_set_file() failed", fts_entry->fts_accpath);
		return (-1);
	}

	if (w->uid != -1 || w->gid != -1) {
		if (chown(fts_entry->fts_accpath, w->uid, w->gid) < 0) {
			warn("%s: chown() failed", fts_entry->fts_accpath);
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
set_acls(struct windows_acl_info *w)
{
	FTS *tree = NULL;
	FTSENT *entry;
	int options = 0;
	char *paths[4];
	int rval;
	struct stat ftsroot_st;
	size_t slen, plen;
	char *relpath = NULL;

	if (w == NULL)
		return (-1);

	if (stat(w->path, &ftsroot_st) < 0) {
		err(EX_OSERR, "%s: stat() failed", w->path);
	}

	paths[0] = w->path;
	paths[1] = NULL;

	if ((w->flags & WA_TRAVERSE) == 0 || (w->flags & WA_RESTORE)) {
		options |= FTS_XDEV;
	}

	if ((tree = fts_open(paths, options, fts_compare)) == NULL)
		err(EX_OSERR, "fts_open");

        slen = strlen(w->source);
        plen = strlen(w->path);

	/* traverse directory hierarchy */
	for (rval = 0; (entry = fts_read(tree)) != NULL;) {
		if ((w->flags & WA_RECURSIVE) == 0) {
			if (entry->fts_level == FTS_ROOTLEVEL){
				rval = set_acl(w, entry);
				break;
			}
		}

		/*
		 * Recursively set permissions for the target path.
		 * In case FTS_XDEV is set, we still need to check st_dev to avoid
		 * resetting permissions on subdatasets (FTS_XDEV will only prevent us
		 * from recursing into directories inside the subdataset.
		 */

		if ( (options & FTS_XDEV) && (ftsroot_st.st_dev != entry->fts_statp->st_dev) ){
			continue;
		}

		switch (entry->fts_info) {
			case FTS_D:
			case FTS_F:
				if (w->root_dev == entry->fts_statp->st_dev) {
					warnx("%s: path resides in boot pool", entry->fts_path);
					return -1;
				}
				if (w->flags & WA_RESTORE) {
					relpath = get_relative_path(entry, plen);

					if (strlen(entry->fts_path) > PATH_MAX) {
						warnx("%s: PATH TOO LONG", entry->fts_path);
						return -1;
					}
					rval = restore_acl(w, relpath, entry, slen);
					break;
				}
				if (w->flags & WA_TRIAL) {
					fprintf(stdout, "depth: %ld, name: %s, full_path: %s\n",
						entry->fts_level, entry->fts_name, entry->fts_path);
					break;
				}
				if (w->flags & WA_STRIP) {
					rval = strip_acl(w, entry);
				}
				else if (w->flags & WA_CHOWN) {
					if ((w->uid == (uid_t)-1 || w->uid == entry->fts_statp->st_uid) &&
					    (w->gid == (gid_t)-1 || w->gid == entry->fts_statp->st_gid)){
						continue;
					}
					if (chown(entry->fts_accpath, w->uid, w->gid) < 0) {
						warn("%s: chown() failed", entry->fts_accpath);
						rval = -1;
					}
					if (w->flags & WA_VERBOSE)
						fprintf(stdout, "%s\n", entry->fts_accpath);

				}
				else {
					rval = set_acl(w, entry);
				}
				break;

			case FTS_ERR:
				warnx("%s: %s", entry->fts_path, strerror(entry->fts_errno));
				rval = -2;
				continue;
		}
		if (rval < 0) {
			err(EX_OSERR, "%s: set_acl() failed", entry->fts_accpath);
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
		w->acls[0].dacl == NULL && w->acls[0].facl == NULL)
		errx(EX_USAGE, "nothing to do");

}

static int
calculate_inherited_acl(struct windows_acl_info *w, acl_t parent_acl, int level)
{
	/*
	 * Generates an inherited directory ACL and file ACL based
	 * on the ACL specified in the parent_acl. Behavior in the absence of
	 * inheriting aces in the parent ACL is as follows: if the parent_acl
	 * is trivial (i.e. can be expressed as posix mode without
	 * information loss), then apply the mode recursively. If the ACL
	 * is non-trivial, then user intention is less clear and so error
	 * out.
	 *
	 * Currently, nfsv41 inheritance is not implemented.
	 */
	int trivial = 0;
	acl_t tmp_acl;
	acl_entry_t entry, file_entry, dir_entry;
	acl_permset_t permset;
	acl_flagset_t flagset, file_flag, dir_flag;
	int entry_id, f_entry_id, d_entry_id, must_set_facl, must_set_dacl;
	int ret = 0;
	entry_id = f_entry_id = d_entry_id = ACL_FIRST_ENTRY;
	must_set_facl = must_set_dacl = true;

	if (w->acls[level].dacl != NULL) {
		acl_free(w->acls[level].dacl);
	}
	if (w->acls[level].facl != NULL) {
		acl_free(w->acls[level].facl);
	}
	/*
	 * Short-circuit for trivial ACLs. If ACL is trivial,
	 * assume that user does not want to apply ACL inheritance rules.
	 */
	if (acl_is_trivial_np(parent_acl, &trivial) != 0) {
		err(EX_OSERR, "acl_is_trivial_np() failed");
	}
	if (trivial) {
		w->acls[level].dacl = acl_dup(parent_acl);
		w->acls[level].facl = acl_dup(parent_acl);
		return ret;
	}

	/* initialize separate directory and file ACLs */
	if ((w->acls[level].dacl = acl_init(ACL_MAX_ENTRIES)) == NULL) {
		err(EX_OSERR, "failed to initialize directory ACL");
	}
	if ((w->acls[level].facl = acl_init(ACL_MAX_ENTRIES)) == NULL) {
		err(EX_OSERR, "failed to initialize file ACL");
	}

	tmp_acl = acl_dup(parent_acl);

	if (tmp_acl == NULL) {
		err(EX_OSERR, "acl_dup() failed");
	}

	while (acl_get_entry(tmp_acl, entry_id, &entry) == 1) {
		entry_id = ACL_NEXT_ENTRY;
		if (acl_get_permset(entry, &permset)) {
			err(EX_OSERR, "acl_get_permset() failed");
		}
		if (acl_get_flagset_np(entry, &flagset)) {
			err(EX_OSERR, "acl_get_flagset_np() failed");
		}

		/* Entry is not inheritable at all. Skip. */
		if ((*flagset & (ACL_ENTRY_DIRECTORY_INHERIT|ACL_ENTRY_FILE_INHERIT)) == 0) {
			continue;
		}

		/* Skip if the ACE has NO_PROPAGATE flag set and does not have INHERIT_ONLY flag. */
		if ((*flagset & ACL_ENTRY_NO_PROPAGATE_INHERIT) &&
		    (*flagset & ACL_ENTRY_INHERIT_ONLY) == 0) {
			continue;
		}

		/*
		 * By the time we've gotten here, we're inheriting something somewhere.
		 * Strip inherit only from the flagset and set ACL_ENTRY_INHERITED.
		 */

		*flagset &= ~ACL_ENTRY_INHERIT_ONLY;
		*flagset |= ACL_ENTRY_INHERITED;

		if ((*flagset & ACL_ENTRY_FILE_INHERIT) == 0) {
			must_set_facl = false;
		}

		/*
		 * Add the entries to the file ACL and directory ACL. Since files and directories
		 * will require differnt flags to be set, we make separate calls to acl_get_flagset_np()
		 * to modify the flagset of the new ACEs.
		 */
		if (must_set_facl) {
			if (acl_create_entry_np(&w->acls[level].facl, &file_entry, f_entry_id) == -1) {
				err(EX_OSERR, "acl_create_entry() failed");
			}
			if (acl_copy_entry(file_entry, entry) == -1) {
				err(EX_OSERR, "acl_create_entry() failed");
			}
			if (acl_get_flagset_np(file_entry, &file_flag)) {
				err(EX_OSERR, "acl_get_flagset_np() failed");
			}
			*file_flag &= ~(ACL_ENTRY_DIRECTORY_INHERIT|ACL_ENTRY_FILE_INHERIT|ACL_ENTRY_NO_PROPAGATE_INHERIT);
			f_entry_id ++;
		}
		if (must_set_dacl) {
			if (acl_create_entry_np(&w->acls[level].dacl, &dir_entry, d_entry_id) == -1) {
				err(EX_OSERR, "acl_create_entry() failed");
			}
			if (acl_copy_entry(dir_entry, entry) == -1) {
				err(EX_OSERR, "acl_create_entry() failed");
			}
			if (acl_get_flagset_np(dir_entry, &dir_flag)) {
				err(EX_OSERR, "acl_get_flagset_np() failed");
			}
			/*
			 * Special handling for NO_PROPAGATE_INHERIT. Original flags at
			 * this point would have been fdin, din, or fin. In the case of
			 * fin, the acl entry must not be added to the dacl (since it only
			 * applies to files).
			 */
			if (*flagset & ACL_ENTRY_NO_PROPAGATE_INHERIT) {
				if ((*flagset & ACL_ENTRY_DIRECTORY_INHERIT) == 0) {
					continue;
				}
				*dir_flag &= ~(ACL_ENTRY_DIRECTORY_INHERIT|ACL_ENTRY_FILE_INHERIT|ACL_ENTRY_NO_PROPAGATE_INHERIT);
			}
			/*
			 * If only FILE_INHERIT is set then turn on INHERIT_ONLY
			 * on directories. This is to prevent ACE from applying to directories.
			 */
			else if ((*flagset & ACL_ENTRY_DIRECTORY_INHERIT) == 0) {
				*dir_flag |= ACL_ENTRY_INHERIT_ONLY;
			}
			d_entry_id ++;
		}
		must_set_dacl = must_set_facl = true;

	}
	acl_free(tmp_acl);
	if ( d_entry_id == 0 || f_entry_id == 0 ) {
		errno = EINVAL;
		warn("%s: acl_set_file() failed. Calculated invalid ACL with no inherited entries.", w->source);
		ret = -1;
	}
	return (ret);
}

static uid_t
id(const char *name, const char *type)
{
	uid_t val;
	char *ep = NULL;

	/*
	 * We know that uid_t's and gid_t's are unsigned longs.
	 */
	errno = 0;
	val = strtoul(name, &ep, 10);
	if (errno || *ep != '\0')
		errx(1, "%s: illegal %s name", name, type);
	return (val);
}

static gid_t
a_gid(const char *s)
{
	struct group *gr = NULL;
	return ((gr = getgrnam(s)) != NULL) ? gr->gr_gid : id(s, "group");
}

static uid_t
a_uid(const char *s)
{
	struct passwd *pw = NULL;
	return ((pw = getpwnam(s)) != NULL) ? pw->pw_uid : id(s, "user");
}

int
main(int argc, char **argv)
{
	int 	ch, ret;
	struct 	windows_acl_info *w;
	acl_t	source_acl;
	char *p = argv[0];
	ch = ret = 0;
	struct stat st;

	if (argc < 2) {
		usage(argv[0]);
	}

	w = new_windows_acl_info();

	while ((ch = getopt(argc, argv, "a:O:G:c:s:p:rftvx")) != -1) {
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
				w->uid = a_uid(optarg);
				break;
			}

			case 'G': {
				w->gid = a_gid(optarg);
				break;
			}

			case 'c':
				w->chroot = realpath(optarg, NULL);
				break;

			case 's':
				w->source = realpath(optarg, NULL);
				break;

			case 'p':
				w->path = realpath(optarg, NULL);
				break;

			case 'r':
				w->flags |= WA_RECURSIVE;
				break;

			case 't':
				w->flags |= WA_TRIAL;
				break;

			case 'v':
				w->flags |= WA_VERBOSE;
				break;

			case 'x':
				w->flags |= WA_TRAVERSE;
				break;

			case 'f':
				w->flags |= WA_FORCE;
				break;

			case '?':
			default:
				usage(argv[0]);
			}
	}

	/* set the source to the destination if we lack -s */
	if (w->source == NULL) {
		if (w->flags & WA_RESTORE) {
			warn("source must be set for restore jobs");
			return (1);
		}
		w->source = w->path;
	}

	if (stat("/", &st) < 0) {
		warn("%s: stat() failed.", "/");
		return (1);
	}
	w->root_dev = st.st_dev;

	if (w->chroot != NULL) {
		if (w->source != NULL) {
			if (strncmp(w->chroot, w->source, strlen(w->chroot)) != 0) {
				warn("%s: path does not lie in chroot path.", w->source);
				free_windows_acl_info(w);
				return (1);
			}
			if (strlen(w->chroot) == strlen(w->source)) {
				w->source = strdup(".");
			}
			else {
				w->source += strlen(w->chroot);
			}
		}
		if (w->path != NULL ) {
			if (strncmp(w->chroot, w->path, strlen(w->chroot)) != 0) {
				warn("%s: path does not lie in chroot path.", w->path);
				free_windows_acl_info(w);
				return (1);
			}
			if (strlen(w->chroot) == strlen(w->path)) {
				w->path = strdup(".");
			}
			else {
				w->path += strlen(w->chroot);
			}
		}
		ret = chdir(w->chroot);
		if (ret == -1) {
			warn("%s: chdir() failed.", w->chroot);
			free_windows_acl_info(w);
			return (1);
		}
		ret = chroot(w->chroot);
		if (ret == -1) {
			warn("%s: chroot() failed.", w->chroot);
			free_windows_acl_info(w);
			return (1);
		}
		printf("path: [%s]\n", w->path);
		if (access(w->path, F_OK) < 0) {
			warn("%s: access() failed after chroot.", w->path);
			free_windows_acl_info(w);
			return (1);
		}
	}

	if (access(w->source, F_OK) < 0) {
		warn("%s: access() failed.", w->source);
		free_windows_acl_info(w);
		return (1);
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
		if (calculate_inherited_acl(w, w->source_acl, 0) != 0) {
			free_windows_acl_info(w);
			return (1);
		}
		if (calculate_inherited_acl(w, w->acls[0].dacl, 1) != 0) {
			free_windows_acl_info(w);
			return (1);
		}
	}

	usage_check(w);

	if (set_acls(w) <0) {
		ret = 1;
	}

	free_windows_acl_info(w);
	return (ret);
}
