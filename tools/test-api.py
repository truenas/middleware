#!/usr/local/bin/python

import os
import sys

import json
import urllib
import urllib2

_w = sys.stdout.write

def freenas_add_headers(request, csrftoken, sessionid, post=False, args=None):
    request.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    request.add_header("Accept-Language", "en-us,en;q=0.5")
    request.add_header("Accept-Encoding", "gzip, deflate")
    request.add_header("Accept-Charset", "ISO-8850-1,utf-8;q=0.7")
    request.add_header("Connection", "keep-alive")
    request.add_header("Cookie", "csrftoken=%s; sessionid=%s" % (csrftoken, sessionid))

    if post:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        if args: 
            request.add_header("Content-Length", len(args))


def freenas_add_json_headers(request, csrftoken, sessionid, post=False, args=None):
    request.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    request.add_header("Accept-Language", "en-us,en;q=0.5")
    request.add_header("Accept-Encoding", "gzip, deflate")
    request.add_header("Accept-Charset", "ISO-8850-1,utf-8;q=0.7")
    request.add_header("Connection", "keep-alive")
    request.add_header("Cookie", "csrftoken=%s; sessionid=%s" % (csrftoken, sessionid))
    request.add_header("X-CSRFToken", "%s" % csrftoken)
    request.add_header("X-Requested-With", "XMLHttpRequest")
    request.add_header("Pragma", "no-cache")
    request.add_header("Cache-Control", "no-cache")
    request.add_header("Content-Type", "application/json-rpc")

    if post:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        if args: 
            request.add_header("Content-Length", len(args))


def freenas_no_redirect(request, args=None):
    class DontRedirect(urllib2.HTTPRedirectHandler):
        def http_error_302(self, req, fp, code, msg, headers):
            infourl = urllib.addinfourl(fp, headers, req.get_full_url())
            infourl.status = code
            infourl.code = code
            return infourl

        http_error_300 = http_error_301 = http_error_303 = http_error_307 = http_error_302

    opener = urllib2.build_opener(DontRedirect)
    urllib2.install_opener(opener)

    return urllib2.urlopen(request, args)


def freenas_get_page(url, csrftoken, sessionid, redirect=True):
    urlopen = urllib2.urlopen if redirect else freenas_no_redirect

    request = urllib2.Request(url)
    freenas_add_headers(request, csrftoken, sessionid)

    response = urlopen(request)
    return response


def freenas_post_page(url, csrftoken, sessionid, redirect=True, args=None):
    urlopen = urllib2.urlopen if redirect else freenas_no_redirect

    request = urllib2.Request(url)
    freenas_add_headers(request, csrftoken, sessionid, True, args)

    response = urlopen(request, args)
    return response


__id = 1 
def freenas_json_call(url, csrftoken, sessionid, method, *args):
    global __id
    urlopen = freenas_no_redirect
    json_url = url + "/plugins/json/"

    py_args = { "method": "%s" % method }
    if args:
        params = []
        for arg in args:
            params.append(arg)
        py_args["params"] = params
    py_args["id"] = __id
    __id += 1

    json_args = json.dumps(py_args)

    request = urllib2.Request(json_url)
    freenas_add_json_headers(request, csrftoken, sessionid, True, json_args)
    response = urlopen(request, json_args)

    py_res = None
    try:
        res1 = response.read()
        res2 = json.loads(res1)
        py_res = json.loads(res2["result"])

    except:
        py_res = None

    return py_res 


def freenas_get_login_page(url):
    csrftoken = sessionid = None

    response = urllib2.urlopen(url)
    headers = response.info()

    set_cookie = headers["set-cookie"]
    parts = set_cookie.split(';')
    for p in parts:
        p = p.strip()

        if p.startswith("csrftoken"):
            csrftoken = p.split('=')[1]

        elif p.startswith("Path"):
            tmp = p.split(',')
            if len(tmp) > 1:
                tmp = tmp[1]
                sessionid = tmp.split('=')[1]

    return csrftoken, sessionid


def freenas_post_login_page(url, csrftoken, sessionid, username, password, next=None):
    args = { "username": username, "password": password, "csrfmiddlewaretoken": csrftoken }
    encoded_args = urllib.urlencode(args) + "&next="
    encoded_args += "&next=%s" % (next if next else "")

    response = freenas_post_page(url, csrftoken, sessionid, False, encoded_args)
    headers = response.info()

    sessionid = None
    set_cookie = headers['set-cookie']

    parts = set_cookie.split(';')
    for p in parts:
        p = p.strip()
        if p.startswith("sessionid"):
            sessionid = p.split('=')[1]
            break

    return csrftoken, sessionid


def freenas_login(url, username, password):
    login_url = url + "/account/login/"

    csrftoken, sessionid = freenas_get_login_page(login_url)
    csrftoken, sessionid = freenas_post_login_page(login_url, csrftoken, sessionid, username, password)

    response = freenas_get_page(url, csrftoken, sessionid)
    return csrftoken, sessionid, response


def freenas_get_logout_page(url, csrftoken, sessionid):
    request = urllib2.Request(url)
    freenas_add_headers(request, csrftoken, sessionid)

    response = freenas_get_page(url, csrftoken, sessionid, False)
    headers = response.info()

    sessionid = None
    set_cookie = headers['set-cookie']

    parts = set_cookie.split(';')
    for p in parts:
        p = p.strip()
        if p.startswith("sessionid"):
            sessionid = p.split('=')[1]
            break

    return csrftoken, sessionid, response


def freenas_logout(url, csrftoken, sessionid):
    logout_url = url + "/account/logout/"
    csrftoken, sessionid, response = freenas_get_logout_page(logout_url, csrftoken, sessionid) 
    return response


def freenas_apicall_test(url, csrftoken, sessionid, unit, method, msg, *args):
    test = "%s.%s" % (unit, method)

    _w("%s: %s: " % (test, msg if msg else ""))
    results = freenas_json_call(url, csrftoken, sessionid, test, *args)
    _w("%s\n" % "ok" if results else "fail")

    return results


_t = freenas_apicall_test


def account_bsdgroups_test(url, csrftoken, sessionid):
    unit = "account.bsdgroups"

    ret = False
    group = "testgroup"

    results = _t(url, csrftoken, sessionid, unit, "create",
        "creating group %s" % group, 8888, group, False)
    if not results:
        return ret

    pk = results[0]["pk"]

    if not _t(url, csrftoken, sessionid, unit, "get",
        "getting group %s" % group, pk):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "set",
        "changing group %s to %s" % (group, "blahgroup"),
        pk, None, "blahgroup"):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "destroy",
        "deleting group %s" % group, pk):
        return ret

    return True

def account_bsdusers_test(url, csrftoken, sessionid):
    unit = "account.bsdusers"

    ret = False
    username = "testuser"

    results = _t(url, csrftoken, sessionid, unit, "create",
        "creating user %s" % username, 8888, username, "mypassword", None,
        "/nonexistent", "/usr/sbin/nologin", "Test User", False, None)
    if not results:
        return ret

    pk = results[0]["pk"]

    if not _t(url, csrftoken, sessionid, unit, "get",
        "getting user %s" % username, pk):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "set",
        "changing user %s to %s" % (username, "blahuser"),
        pk, None, None, "blahuser"):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "destroy",
        "deleting user %s" % username, pk):
        return ret

    return True

def network_globalconfiguration_test(url, csrftoken, sessionid):
    unit = "network.globalconfiguration"

    ret = False
    hostname = "testhost"

    results = _t(url, csrftoken, sessionid, unit, "create",
        "creating host %s" % hostname, hostname, "freenas.org",
        "10.0.0.1", None, "10.0.0.1", None, None)
    if not results:
        return ret

    pk = results[0]["pk"]

    if not _t(url, csrftoken, sessionid, unit, "get", None, pk):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "set",
        "changing host %s to %s" % (hostname, "blahhost"),
        pk, "blahhost"):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "destroy",
        "deleting host %s" % hostname, pk):
        return ret

    return True

def network_interfaces_test(url, csrftoken, sessionid):
    unit = "network.interfaces"

    ret = False
    ip = "192.168.5.33"
    iface = "em9"

    results = _t(url, csrftoken, sessionid, unit, "create",
        "creating interface %s" % iface, iface, "Secondary interface",
        None, ip, "24", None, None, None, None)
    if not results:
        return ret

    pk = results[0]["pk"]

    if not _t(url, csrftoken, sessionid, unit, "get",
        "getting interface %s" % iface, pk):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "set",
        "changing %s to %s" % (ip, "192.168.5.44"), pk, None,
        None, None, "192.168.5.44"):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "destroy",
        "deleting interface %s" % iface, pk):
        return ret

    return True

# this does not work right now
def network_alias_test(url, csrftoken, sessionid):
    unit = "network.alias"

    ret = False
    alias = "192.168.5.33"
    iface = "em9"

    results = _t(url, csrftoken, sessionid, unit, "create",
        "creating alias %s on iface %s" % (alias, iface),
         iface, alias, "24", None, None)
    if not results:
        return ret

    pk = results[0]["pk"]

    if not _t(url, csrftoken, sessionid, unit, "get",
        "getting alias %s" % alias, pk):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "set",
        "changing %s to %s" % (alias, "192.168.5.44"),
        pk, None, "192.168.5.44"):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "destroy",
        "deleting alias %s" % alias, pk):
        return ret

    return True

def services_services_test(url, csrftoken, sessionid):
    unit = "services.services"

    ret = False
    srv = "BLAH"

    results = _t(url, csrftoken, sessionid, unit, "create",
        "creating service %s" % srv, srv, True)
    if not results:
        return ret

    pk = results[0]["pk"]

    if not _t(url, csrftoken, sessionid, unit, "get",
        "getting service %s" % srv, pk):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "set",
        "changing service %s to %s" % (srv, "FOO"),
        pk, "FOO"):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "destroy",
        "deleting service %s" % srv, pk):
        return ret

    return True

def services_cifs_test(url, csrftoken, sessionid):
    unit = "services.cifs"

    ret = False

    results = _t(url, csrftoken, sessionid, unit, "create",
        "creating CIFS service", "share", "freenas", "WORKGROUP")
    if not results:
        return ret

    pk = results[0]["pk"]

    if not _t(url, csrftoken, sessionid, unit, "get",
        "getting CIFS service", pk):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "set",
        "changing CIFS service %s to %s" % ("freenas", "blahnas"),
        pk, None, "blahnas"):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "destroy",
        "deleting CIFS service", pk):
        return ret

    return True

def services_afp_test(url, csrftoken, sessionid):
    unit = "services.afp"

    ret = False
    name = "MYAFPSHARE"

    results = _t(url, csrftoken, sessionid, unit, "create",
        "creating AFP service", name)
    if not results:
        return ret

    pk = results[0]["pk"]

    if not _t(url, csrftoken, sessionid, unit, "get",
        "getting AFP service", pk):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "set",
        "changing AFP service %s to %s" % (name, "BLAHAFPSHARE"),
        pk, "BLAHAFPSHARE"):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "destroy",
        "deleting AFP service", pk):
        return ret

    return True

def services_nfs_test(url, csrftoken, sessionid):
    unit = "services.nfs"

    ret = False
    name = "MYAFPSHARE"

    results = _t(url, csrftoken, sessionid, unit, "create",
        "creating NFS service", 4)
    if not results:
        return ret

    pk = results[0]["pk"]

    if not _t(url, csrftoken, sessionid, unit, "get",
        "getting NFS service", pk):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "set",
        "changing NFS service %d to %d" % (4, 8),
        pk, 8):
        return ret

    if not _t(url, csrftoken, sessionid, unit, "destroy",
        "deleting NFS service", pk):
        return ret

    return True


def sharing_cifs_share_test(url, csrftoken, sessionid):
    pass

def sharing_afp_share_test(url, csrftoken, sessionid):
    pass

def sharing_nfs_share_test(url, csrftoken, sessionid):
    pass


def main():
    if len(sys.argv) != 4:
        sys.stderr.write("Usage: %s [user] [pass] [url]\n\n" % sys.argv[0])
        sys.exit(1)

    u = sys.argv[1]
    p = sys.argv[2]
    url = sys.argv[3]

    csrftoken, sessionid, response = freenas_login(url, u, p)

    #account_bsdgroups_test(url, csrftoken, sessionid)
    #account_bsdusers_test(url, csrftoken, sessionid)

    #network_globalconfiguration_test(url, csrftoken, sessionid)
    #network_interfaces_test(url, csrftoken, sessionid)
    #network_alias_test(url, csrftoken, sessionid)

    #services_services_test(url, csrftoken, sessionid)
    #services_cifs_test(url, csrftoken, sessionid)
    #services_afp_test(url, csrftoken, sessionid)
    #services_nfs_test(url, csrftoken, sessionid)

    sharing_cifs_share_test(url, csrftoken, sessionid)
    sharing_afp_share_test(url, csrftoken, sessionid)
    sharing_nfs_share_test(url, csrftoken, sessionid)

    freenas_logout(url, csrftoken, sessionid)

if __name__ == '__main__':
    main()
