#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
url = conn.url + 'system/shutdown/'
auth = conn.auth

r = requests.post(url, auth = auth, headers = headers)
