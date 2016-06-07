#include <sys/param.h>
#include <netinet/in.h>

#include <errno.h>
#include <stdlib.h>
#include <pwd.h>
#include <grp.h>
#include <nss.h>
#include <nsswitch.h>
#include <netdb.h>

extern enum nss_status _nss_ldap_getgrent_r(struct group *, char *, size_t,
    int *);
extern enum nss_status _nss_ldap_getgrnam_r(const char *, struct group *,
    char *, size_t, int *);
extern enum nss_status _nss_ldap_getgrgid_r(gid_t gid, struct group *, char *,
    size_t, int *);
extern enum nss_status _nss_ldap_setgrent(void);
extern enum nss_status _nss_ldap_endgrent(void);
extern enum nss_status _nss_ldap_initgroups_dyn(const char *, gid_t, long int *,
			   long int *, gid_t **, long int, int *);

extern enum nss_status _nss_ldap_getpwent_r(struct passwd *, char *, size_t,
    int *);
extern enum nss_status _nss_ldap_getpwnam_r(const char *, struct passwd *,
    char *, size_t, int *);
extern enum nss_status _nss_ldap_getpwuid_r(gid_t gid, struct passwd *, char *,
    size_t, int *);
extern enum nss_status _nss_ldap_setpwent(void);
extern enum nss_status _nss_ldap_endpwent(void);

extern enum nss_status _nss_ldap_gethostbyname_r (const char *name, struct hostent * result,
			   char *buffer, size_t buflen, int *errnop,
			   int *h_errnop);

extern enum nss_status _nss_ldap_gethostbyname2_r (const char *name, int af, struct hostent * result,
			    char *buffer, size_t buflen, int *errnop,
			    int *h_errnop);
extern enum nss_status _nss_ldap_gethostbyaddr_r (struct in_addr * addr, int len, int type,
			   struct hostent * result, char *buffer,
			   size_t buflen, int *errnop, int *h_errnop);

struct __netgrent;
extern enum nss_status _nss_ldap_netgrp_load_result(struct __netgrent *result,
			   char **hostp, char **userp, char **domp);
extern enum nss_status _nss_ldap_getnetgrent_r(struct __netgrent *result, char *buffer,
			   size_t buflen, int *errnop);
extern enum nss_status _nss_ldap_setnetgrent(char *group, struct __netgrent *result);
extern enum nss_status _nss_ldap_endnetgrent(struct __netgrent *result);

NSS_METHOD_PROTOTYPE(__nss_compat_getgrnam_r);
NSS_METHOD_PROTOTYPE(__nss_compat_getgrgid_r);
NSS_METHOD_PROTOTYPE(__nss_compat_getgrent_r);
NSS_METHOD_PROTOTYPE(__nss_compat_setgrent);
NSS_METHOD_PROTOTYPE(__nss_compat_endgrent);
static NSS_METHOD_PROTOTYPE(__freebsd_getgroupmembership);

NSS_METHOD_PROTOTYPE(__nss_compat_getpwnam_r);
NSS_METHOD_PROTOTYPE(__nss_compat_getpwuid_r);
NSS_METHOD_PROTOTYPE(__nss_compat_getpwent_r);
NSS_METHOD_PROTOTYPE(__nss_compat_setpwent);
NSS_METHOD_PROTOTYPE(__nss_compat_endpwent);

NSS_METHOD_PROTOTYPE(__nss_compat_gethostbyname);
NSS_METHOD_PROTOTYPE(__nss_compat_gethostbyname2);
NSS_METHOD_PROTOTYPE(__nss_compat_gethostbyaddr);

static NSS_METHOD_PROTOTYPE(__nss_compat_getnetgrent_r);
static NSS_METHOD_PROTOTYPE(__nss_compat_setnetgrent);
static NSS_METHOD_PROTOTYPE(__nss_compat_endnetgrent);

static ns_mtab methods[] = {
{ NSDB_GROUP, "getgrnam_r", __nss_compat_getgrnam_r, _nss_ldap_getgrnam_r },
{ NSDB_GROUP, "getgrgid_r", __nss_compat_getgrgid_r, _nss_ldap_getgrgid_r },
{ NSDB_GROUP, "getgrent_r", __nss_compat_getgrent_r, _nss_ldap_getgrent_r },
{ NSDB_GROUP, "setgrent",   __nss_compat_setgrent,   _nss_ldap_setgrent },
{ NSDB_GROUP, "endgrent",   __nss_compat_endgrent,   _nss_ldap_endgrent },
{ NSDB_GROUP, "getgroupmembership",  __freebsd_getgroupmembership, NULL },

{ NSDB_PASSWD, "getpwnam_r", __nss_compat_getpwnam_r, _nss_ldap_getpwnam_r },
{ NSDB_PASSWD, "getpwuid_r", __nss_compat_getpwuid_r, _nss_ldap_getpwuid_r },
{ NSDB_PASSWD, "getpwent_r", __nss_compat_getpwent_r, _nss_ldap_getpwent_r },
{ NSDB_PASSWD, "setpwent",   __nss_compat_setpwent,   _nss_ldap_setpwent },
{ NSDB_PASSWD, "endpwent",   __nss_compat_endpwent,   _nss_ldap_endpwent },

{ NSDB_HOSTS, "gethostbyname", __nss_compat_gethostbyname, _nss_ldap_gethostbyname_r },
{ NSDB_HOSTS, "gethostbyaddr", __nss_compat_gethostbyaddr, _nss_ldap_gethostbyaddr_r },
{ NSDB_HOSTS, "gethostbyname2", __nss_compat_gethostbyname2, _nss_ldap_gethostbyname2_r },

{ NSDB_NETGROUP, "getnetgrent_r", __nss_compat_getnetgrent_r, _nss_ldap_getnetgrent_r },
{ NSDB_NETGROUP, "setnetgrent", __nss_compat_setnetgrent, _nss_ldap_setnetgrent },
{ NSDB_NETGROUP, "endnetgrent", __nss_compat_endnetgrent, _nss_ldap_endnetgrent },

{ NSDB_GROUP_COMPAT, "getgrnam_r", __nss_compat_getgrnam_r, _nss_ldap_getgrnam_r },
{ NSDB_GROUP_COMPAT, "getgrgid_r", __nss_compat_getgrgid_r, _nss_ldap_getgrgid_r },
{ NSDB_GROUP_COMPAT, "getgrent_r", __nss_compat_getgrent_r, _nss_ldap_getgrent_r },
{ NSDB_GROUP_COMPAT, "setgrent",   __nss_compat_setgrent,   _nss_ldap_setgrent },
{ NSDB_GROUP_COMPAT, "endgrent",   __nss_compat_endgrent,   _nss_ldap_endgrent },

{ NSDB_PASSWD_COMPAT, "getpwnam_r", __nss_compat_getpwnam_r, _nss_ldap_getpwnam_r },
{ NSDB_PASSWD_COMPAT, "getpwuid_r", __nss_compat_getpwuid_r, _nss_ldap_getpwuid_r },
{ NSDB_PASSWD_COMPAT, "getpwent_r", __nss_compat_getpwent_r, _nss_ldap_getpwent_r },
{ NSDB_PASSWD_COMPAT, "setpwent",   __nss_compat_setpwent,   _nss_ldap_setpwent },
{ NSDB_PASSWD_COMPAT, "endpwent",   __nss_compat_endpwent,   _nss_ldap_endpwent },

};


ns_mtab *
nss_module_register(const char *source, unsigned int *mtabsize,
    nss_module_unregister_fn *unreg)
{
	*mtabsize = sizeof(methods)/sizeof(methods[0]);
	*unreg = NULL;
	return (methods);
}

int __nss_compat_gethostbyname(void *retval, void *mdata, va_list ap)
{
	enum nss_status 	(*fn)(const char *, struct hostent *, char *, size_t, int *, int *);
	const char 	*name;
	struct hostent 	*result;
	char 		buffer[1024];
	size_t 		buflen = 1024;
	int 		errnop;
	int		h_errnop;
	int		af;
	enum nss_status	status;
	fn = mdata;
	name = va_arg(ap, const char*);
	af = va_arg(ap,int);
	result = va_arg(ap,struct hostent *);
	status = fn(name, result, buffer, buflen, &errnop, &h_errnop);
	status = __nss_compat_result(status,errnop);
	h_errno = h_errnop;
	return (status);
}

int __nss_compat_gethostbyname2(void *retval, void *mdata, va_list ap)
{
	enum nss_status 	(*fn)(const char *, struct hostent *, char *, size_t, int *, int *);
	const char 	*name;
	struct hostent 	*result;
	char 		buffer[1024];
	size_t 		buflen = 1024;
	int 		errnop;
	int		h_errnop;
	int		af;
	enum nss_status	status;
	fn = mdata;
	name = va_arg(ap, const char*);
	af = va_arg(ap,int);
	result = va_arg(ap,struct hostent *);
	status = fn(name, result, buffer, buflen, &errnop, &h_errnop);
	status = __nss_compat_result(status,errnop);
	h_errno = h_errnop;
	return (status);
}

int __nss_compat_gethostbyaddr(void *retval, void *mdata, va_list ap)
{
	struct in_addr 	*addr;
	int 		len;
	int 		type;
	struct hostent	*result;
	char 		buffer[1024];
	size_t		buflen = 1024;
	int		errnop;
	int		h_errnop;
	enum nss_status (*fn)(struct in_addr *, int, int, struct hostent *, char *, size_t, int *, int *);
	enum nss_status status;
	fn = mdata;
	addr = va_arg(ap, struct in_addr*);
	len = va_arg(ap,int);
	type = va_arg(ap,int);
	result = va_arg(ap, struct hostent*);
	status = fn(addr, len, type, result, buffer, buflen, &errnop, &h_errnop);
	status = __nss_compat_result(status,errnop);
	h_errno = h_errnop;
	return (status);
}

static int
__gr_addgid(gid_t gid, gid_t *groups, int maxgrp, int *groupc)
{
	int	ret, dupc;

	/* skip duplicates */
	for (dupc = 0; dupc < MIN(maxgrp, *groupc); dupc++) {
		if (groups[dupc] == gid)
			return 1;
	}

	ret = 1;
	if (*groupc < maxgrp)			/* add this gid */
		groups[*groupc] = gid;
	else
		ret = 0;
	(*groupc)++;
	return ret;
}

static int __freebsd_getgroupmembership(void *retval, void *mdata, va_list ap)
{
	int err;
	enum nss_status s;
	const char *user 	= va_arg(ap, const char *);
	gid_t group 		= va_arg(ap, gid_t);
	gid_t *groups 		= va_arg(ap, gid_t *);
	int limit 		= va_arg(ap, int);
	int *size 		= va_arg(ap, int*);
	gid_t *tmpgroups;
	long int lstart, lsize;
	int i;

	tmpgroups = malloc(limit * sizeof(gid_t));
	if (tmpgroups == NULL)
		return NS_TRYAGAIN;

	/* insert primary membership */
	__gr_addgid(group, groups, limit, size);

	lstart = 0;
	lsize = limit;
	s = _nss_ldap_initgroups_dyn(user, group, &lstart, &lsize,
		&tmpgroups, 0, &err);
	if (s == NSS_STATUS_SUCCESS) {
		for (i = 0; i < lstart; i++)
			 __gr_addgid(tmpgroups[i], groups, limit, size);
		s = NSS_STATUS_NOTFOUND;
	}

	free(tmpgroups);

	return __nss_compat_result(s, err);
}

static void *_netgr_result;

static int
__nss_compat_getnetgrent_r(void *retval, void *mdata, va_list ap)
{
	char **hostp, **userp, **domp;
	char *buffer;
	size_t bufsize;
	enum nss_status rv;
	int *errorp;
	int ret;

	hostp = va_arg(ap, char **);
	userp = va_arg(ap, char **);
	domp = va_arg(ap, char **);
	buffer = va_arg(ap, char *);
	bufsize = va_arg(ap, size_t);
	errorp = va_arg(ap, int *);

	do {
		*errorp = 0;
		rv = _nss_ldap_getnetgrent_r(_netgr_result, buffer, bufsize,
		    errorp);
		ret = __nss_compat_result(rv, *errorp);
		if (ret != NS_SUCCESS)
			return (ret);
		rv = _nss_ldap_netgrp_load_result(_netgr_result, hostp, userp,
		    domp);
		ret = __nss_compat_result(rv, 0);
	} while (ret == NS_TRYAGAIN);

	return (NS_SUCCESS);
}

extern size_t _nss_ldap_netgrent_sz;

static int
__nss_compat_setnetgrent(void *retval, void *mdata, va_list ap)
{
	const char *netgroup;
	int ret;

	netgroup = va_arg(ap, const char *);

	if (_netgr_result != NULL)
		free(_netgr_result);
	_netgr_result = calloc(1, _nss_ldap_netgrent_sz);
	if (_netgr_result == NULL)
		return (NS_TRYAGAIN);

	return (_nss_ldap_setnetgrent(netgroup, _netgr_result));
}

static int
__nss_compat_endnetgrent(void *retval, void *mdata, va_list ap)
{
	int ret;

	ret = _nss_ldap_endnetgrent(_netgr_result);
	free(_netgr_result);
	_netgr_result = NULL;
	return (ret);
}
