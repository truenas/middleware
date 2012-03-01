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
    ret = False

    unit = "account.bsdgroups"
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
    ret = False

    unit = "account.bsdusers"
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
    ret = False

    unit = "network.globalconfiguration"
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

def main():
    if len(sys.argv) != 4:
        sys.stderr.write("Usage: %s [user] [pass] [url]\n\n" % sys.argv[0])
        sys.exit(1)

    u = sys.argv[1]
    p = sys.argv[2]
    url = sys.argv[3]

    csrftoken, sessionid, response = freenas_login(url, u, p)

    account_bsdgroups_test(url, csrftoken, sessionid)
    account_bsdusers_test(url, csrftoken, sessionid)
    network_globalconfiguration_test(url, csrftoken, sessionid)

    freenas_logout(url, csrftoken, sessionid)

if __name__ == '__main__':
    main()
