#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

auth = conn.auth
url = conn.url + 'system/alert/'

r = requests.get(url, auth = auth)
result = json.loads(r.text)
i = 0
for i in range(0,len(result)):
  for items in result[i]:
    print items+':', result[i][items]
