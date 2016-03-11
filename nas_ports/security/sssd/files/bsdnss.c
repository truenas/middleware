#include <errno.h>
#include <sys/param.h>
#include <netinet/in.h>
#include <pwd.h>
#include <grp.h>
#include <nss.h>
#include <netdb.h>

extern enum nss_status _nss_sss_getgrent_r(struct group *, char *, size_t,
                                           int *);
extern enum nss_status _nss_sss_getgrnam_r(const char *, struct group *,
                                           char *, size_t, int *);
extern enum nss_status _nss_sss_getgrgid_r(gid_t gid, struct group *, char *,
                                           size_t, int *);
extern enum nss_status _nss_sss_setgrent(void);
extern enum nss_status _nss_sss_endgrent(void);

extern enum nss_status _nss_sss_getpwent_r(struct passwd *, char *, size_t,
                                           int *);
extern enum nss_status _nss_sss_getpwnam_r(const char *, struct passwd *,
                                           char *, size_t, int *);
extern enum nss_status _nss_sss_getpwuid_r(gid_t gid, struct passwd *, char *,
                                           size_t, int *);
extern enum nss_status _nss_sss_setpwent(void);
extern enum nss_status _nss_sss_endpwent(void);

extern enum nss_status _nss_sss_gethostbyname_r(const char *name,
                                                struct hostent * result,
                                                char *buffer, size_t buflen,
                                                int *errnop,
                                                int *h_errnop);

extern enum nss_status _nss_sss_gethostbyname2_r(const char *name, int af,
                                                 struct hostent * result,
                                                 char *buffer, size_t buflen,
                                                 int *errnop,
                                                 int *h_errnop);
extern enum nss_status _nss_sss_gethostbyaddr_r(struct in_addr * addr, int len,
                                                int type,
                                                struct hostent * result,
                                                char *buffer, size_t buflen,
                                                int *errnop, int *h_errnop);

extern enum nss_status _nss_sss_getgroupmembership(const char *uname,
                                                   gid_t agroup, gid_t *groups,
                                                   int maxgrp, int *grpcnt);

NSS_METHOD_PROTOTYPE(__nss_compat_getgroupmembership);
NSS_METHOD_PROTOTYPE(__nss_compat_getgrnam_r);
NSS_METHOD_PROTOTYPE(__nss_compat_getgrgid_r);
NSS_METHOD_PROTOTYPE(__nss_compat_getgrent_r);
NSS_METHOD_PROTOTYPE(__nss_compat_setgrent);
NSS_METHOD_PROTOTYPE(__nss_compat_endgrent);

NSS_METHOD_PROTOTYPE(__nss_compat_getpwnam_r);
NSS_METHOD_PROTOTYPE(__nss_compat_getpwuid_r);
NSS_METHOD_PROTOTYPE(__nss_compat_getpwent_r);
NSS_METHOD_PROTOTYPE(__nss_compat_setpwent);
NSS_METHOD_PROTOTYPE(__nss_compat_endpwent);

NSS_METHOD_PROTOTYPE(__nss_compat_gethostbyname);
NSS_METHOD_PROTOTYPE(__nss_compat_gethostbyname2);
NSS_METHOD_PROTOTYPE(__nss_compat_gethostbyaddr);

static ns_mtab methods[] = {
{ NSDB_GROUP, "getgrnam_r", __nss_compat_getgrnam_r, _nss_sss_getgrnam_r },
{ NSDB_GROUP, "getgrgid_r", __nss_compat_getgrgid_r, _nss_sss_getgrgid_r },
{ NSDB_GROUP, "getgrent_r", __nss_compat_getgrent_r, _nss_sss_getgrent_r },
{ NSDB_GROUP, "getgroupmembership",   __nss_compat_getgroupmembership,   _nss_sss_getgroupmembership },
{ NSDB_GROUP, "setgrent",   __nss_compat_setgrent,   _nss_sss_setgrent },
{ NSDB_GROUP, "endgrent",   __nss_compat_endgrent,   _nss_sss_endgrent },

{ NSDB_PASSWD, "getpwnam_r", __nss_compat_getpwnam_r, _nss_sss_getpwnam_r },
{ NSDB_PASSWD, "getpwuid_r", __nss_compat_getpwuid_r, _nss_sss_getpwuid_r },
{ NSDB_PASSWD, "getpwent_r", __nss_compat_getpwent_r, _nss_sss_getpwent_r },
{ NSDB_PASSWD, "setpwent",   __nss_compat_setpwent,   _nss_sss_setpwent },
{ NSDB_PASSWD, "endpwent",   __nss_compat_endpwent,   _nss_sss_endpwent },

// { NSDB_HOSTS, "gethostbyname", __nss_compat_gethostbyname, _nss_sss_gethostbyname_r },
//{ NSDB_HOSTS, "gethostbyaddr", __nss_compat_gethostbyaddr, _nss_sss_gethostbyaddr_r },
//{ NSDB_HOSTS, "gethostbyname2", __nss_compat_gethostbyname2, _nss_sss_gethostbyname2_r },

{ NSDB_GROUP_COMPAT, "getgrnam_r", __nss_compat_getgrnam_r, _nss_sss_getgrnam_r },
{ NSDB_GROUP_COMPAT, "getgrgid_r", __nss_compat_getgrgid_r, _nss_sss_getgrgid_r },
{ NSDB_GROUP_COMPAT, "getgrent_r", __nss_compat_getgrent_r, _nss_sss_getgrent_r },
{ NSDB_GROUP_COMPAT, "setgrent",   __nss_compat_setgrent,   _nss_sss_setgrent },
{ NSDB_GROUP_COMPAT, "endgrent",   __nss_compat_endgrent,   _nss_sss_endgrent },

{ NSDB_PASSWD_COMPAT, "getpwnam_r", __nss_compat_getpwnam_r, _nss_sss_getpwnam_r },
{ NSDB_PASSWD_COMPAT, "getpwuid_r", __nss_compat_getpwuid_r, _nss_sss_getpwuid_r },
{ NSDB_PASSWD_COMPAT, "getpwent_r", __nss_compat_getpwent_r, _nss_sss_getpwent_r },
{ NSDB_PASSWD_COMPAT, "setpwent",   __nss_compat_setpwent,   _nss_sss_setpwent },
{ NSDB_PASSWD_COMPAT, "endpwent",   __nss_compat_endpwent,   _nss_sss_endpwent },

};


ns_mtab *
nss_module_register(const char *source, unsigned int *mtabsize,
                    nss_module_unregister_fn *unreg)
{
    *mtabsize = sizeof(methods)/sizeof(methods[0]);
    *unreg = NULL;
    return (methods);
}

int __nss_compat_getgroupmembership(void *retval, void *mdata, va_list ap)
{
  int (*fn)(const char *, gid_t, gid_t *, int, int *);

  const char *uname;
  gid_t agroup;
  gid_t *groups;
  int maxgrp;
  int *grpcnt;
  int errnop = 0;
  enum nss_status status;

  fn = mdata;
  uname = va_arg(ap, const char *);
  agroup = va_arg(ap, gid_t);
  groups = va_arg(ap, gid_t *);
  maxgrp = va_arg(ap, int);
  grpcnt = va_arg(ap, int *);
  status = fn(uname, agroup, groups, maxgrp, grpcnt);
  status = __nss_compat_result(status, errnop);
  return (status);
}

int __nss_compat_gethostbyname(void *retval, void *mdata, va_list ap)
{
    enum nss_status (*fn)(const char *, struct hostent *, char *, size_t, int *, int *);
    const char *name;
    struct hostent *result;
    char buffer[1024];
    size_t buflen = 1024;
    int errnop;
    int h_errnop;
    int af;
    enum nss_status status;

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
    enum nss_status (*fn)(const char *, struct hostent *, char *, size_t, int *, int *);
    const char *name;
    struct hostent *result;
    char buffer[1024];
    size_t buflen = 1024;
    int errnop;
    int h_errnop;
    int af;
    enum nss_status status;

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
    struct in_addr *addr;
    int len;
    int type;
    struct hostent *result;
    char buffer[1024];
    size_t buflen = 1024;
    int errnop;
    int h_errnop;
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
