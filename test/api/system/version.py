#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

auth = conn.auth
url = conn.url + 'system/version/'
headers = conn.headers

r = requests.get(url, auth = auth)
result = json.loads(r.text)
for items in result:
  print items+':', result[items]
