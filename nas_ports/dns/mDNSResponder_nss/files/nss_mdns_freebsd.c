#include <sys/param.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netdb.h>
#include <nsswitch.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <syslog.h>

extern int _nss_mdns_gethostbyname2_r(const char *, int,
		struct hostent *, char *, size_t, int *, int *);
extern int _nss_mdns_gethostbyaddr_r(const void *, socklen_t, int,
		struct hostent *, char *, size_t, int *, int *);

static NSS_METHOD_PROTOTYPE(__nss_compat_gethostbyname2_r);
static NSS_METHOD_PROTOTYPE(__nss_compat_gethostbyaddr_r);
static NSS_METHOD_PROTOTYPE(__nss_compat_getaddrinfo);

static ns_mtab methods[] = {
	{ NSDB_HOSTS, "gethostbyname_r", __nss_compat_gethostbyname2_r, NULL },
	{ NSDB_HOSTS, "gethostbyname2_r", __nss_compat_gethostbyname2_r, NULL },
	{ NSDB_HOSTS, "gethostbyaddr_r", __nss_compat_gethostbyaddr_r, NULL },
	{ NSDB_HOSTS, "getaddrinfo", __nss_compat_getaddrinfo, NULL },
};

ns_mtab *
nss_module_register(const char *source, unsigned int *mtabsize,
		nss_module_unregister_fn *unreg)
{
	*mtabsize = sizeof(methods)/sizeof(methods[0]);
	*unreg = NULL;
	return methods;
}

static int
__nss_compat_gethostbyname2_r(void *retval, void *mdata, va_list ap)
{
	int s;

	const char *name;
	int af;
	struct hostent *hptr;
	char *buffer;
	size_t buflen;
	int *errnop;
	int *h_errnop;

	name = va_arg(ap, const char *);
	af = va_arg(ap, int);
	hptr = va_arg(ap, struct hostent *);
	buffer = va_arg(ap, char *);
	buflen = va_arg(ap, size_t);
	errnop = va_arg(ap, int *);
	h_errnop = va_arg(ap, int *);

	s = _nss_mdns_gethostbyname2_r(
			name, af, hptr, buffer, buflen, errnop, h_errnop);
	*(struct hostent **)retval = (s == NS_SUCCESS) ? hptr : NULL;

	return s;
}

static int
__nss_compat_gethostbyaddr_r(void *retval, void *mdata, va_list ap)
{
	int s;
	
	const void *addr;
	socklen_t addrlen;
	int af;
	struct hostent *hptr;
	char *buffer;
	size_t buflen;
	int *errnop;
	int *h_errnop;

    addr = va_arg(ap, const void *);
    addrlen = va_arg(ap, socklen_t);
    af = va_arg(ap, int);
    hptr = va_arg(ap, struct hostent *);
    buffer = va_arg(ap, char *);
    buflen = va_arg(ap, size_t);
    errnop = va_arg(ap, int *);
    h_errnop = va_arg(ap, int *);

	s = _nss_mdns_gethostbyaddr_r(
			addr, addrlen, af, hptr, buffer, buflen, errnop, h_errnop);
	*(struct hostent **)retval = (s == NS_SUCCESS) ? hptr : NULL;

	return s;
} 

static void
aiforaf(const char *name, int af, struct addrinfo *pai, struct addrinfo **aip)
{
	int s;
	struct hostent host;
	char hostbuf[8*1024];
	int err, herr;
	char **addrp;
	char addrstr[INET6_ADDRSTRLEN];
	struct addrinfo hints, *res0, *res;

	s = _nss_mdns_gethostbyname2_r(name, af, &host, hostbuf, sizeof(hostbuf),
			&err, &herr);
	if (s != NS_SUCCESS)
		return;

	for (addrp = host.h_addr_list; *addrp; addrp++) {
		/* XXX this sucks, but get_ai is not public */
		if (!inet_ntop(host.h_addrtype, *addrp,
			       addrstr, sizeof(addrstr)))
			continue;
		hints = *pai;
		hints.ai_flags = AI_NUMERICHOST;
		hints.ai_family = af;
		if (getaddrinfo(addrstr, NULL, &hints, &res0))
			continue;
		for (res = res0; res; res = res->ai_next)
			res->ai_flags = pai->ai_flags;

		(*aip)->ai_next = res0;
		while ((*aip)->ai_next)
			*aip = (*aip)->ai_next;
	}
}

static int
__nss_compat_getaddrinfo(void *retval, void *mdata, va_list ap)
{
	struct addrinfo sentinel, *cur;
	const char *name;
	struct addrinfo *ai;

	name  = va_arg(ap, char *);
	ai = va_arg(ap, struct addrinfo *);

	memset(&sentinel, 0, sizeof(sentinel));
	cur = &sentinel;

	if ((ai->ai_family == AF_UNSPEC) || (ai->ai_family == AF_INET6))
		aiforaf(name, AF_INET6, ai, &cur);
	if ((ai->ai_family == AF_UNSPEC) || (ai->ai_family == AF_INET))
		aiforaf(name, AF_INET, ai, &cur);

	if (!sentinel.ai_next) {
		h_errno = HOST_NOT_FOUND;
		return NS_NOTFOUND;
	}
	*((struct addrinfo **)retval) = sentinel.ai_next;

	return NS_SUCCESS;
}

