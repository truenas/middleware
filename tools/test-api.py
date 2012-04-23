#!/usr/local/bin/python

import os
import sys
import time
import jsonrpclib
import urllib2

import oauth2 as oauth

class OAuthTransport(jsonrpclib.jsonrpc.SafeTransport):
    def __init__(self, host, verbose=None, use_datetime=0, key=None, secret=None):
        jsonrpclib.jsonrpc.SafeTransport.__init__(self)
        self.verbose = verbose
        self._use_datetime = use_datetime
        self.host = host
        self.key = key
        self.secret = secret

    def oauth_request(self, url, moreparams={}, body=''):
        params = {                                           
            'oauth_version': "1.0",
            'oauth_nonce': oauth.generate_nonce(),
            'oauth_timestamp': int(time.time())
        }
        consumer = oauth.Consumer(key=self.key, secret=self.secret)
        params['oauth_consumer_key'] = consumer.key
        params.update(moreparams)
       
        req = oauth.Request(method='POST', url=url, parameters=params, body=body)
        signature_method = oauth.SignatureMethod_HMAC_SHA1()
        req.sign_request(signature_method, consumer, None)
        return req

    def request(self, host, handler, request_body, verbose=0):
        request = self.oauth_request(url=self.host, body=request_body)
        req = urllib2.Request(request.to_url())
        req.add_header('Content-Type', 'text/json')
        req.add_data(request_body)
        f = urllib2.urlopen(req)
        return(self.parse_response(f))


def get_config(path):
    f = open(path)
    lines = f.readlines()
    f.close()

    url = key = secret = None
    for l in lines:
        l = l.strip()

        if l.startswith("#"):
            continue 

        if l.startswith("key"):
            pair = l.split('=')
            if len(pair) > 1:
                key = pair[1].strip()

        elif l.startswith("secret"):
            pair = l.split('=')
            if len(pair) > 1:
                secret = pair[1].strip()

        elif l.startswith("url"):
            pair = l.split('=')
            if len(pair) > 1:
                url = pair[1].strip()

    if not url or not key or not secret:
        return None

    return url, key, secret

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: %s <config>\n" % sys.argv[0])
        sys.exit(1)

    try:
        url, key, secret = get_config(sys.argv[1])

    except:
        sys.stderr.write("invalid config file\n")
        sys.exit(1)

    trans = OAuthTransport(url, key=key, secret=secret)
    s = jsonrpclib.Server(url, transport=trans)

#    print s.plugins.plugins.get("transmission")
#    print s.services.activedirectory.get()
#    print s.account.bsdusers.get()

    sys.exit(0)


if __name__ == "__main__":
    main()
