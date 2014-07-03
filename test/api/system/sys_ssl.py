#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

auth = conn.auth
url = conn.url + 'system/ssl/'
headers = conn.headers
payload =  {
          "ssl_city": "Curitiba",
          "ssl_common": "iXsystems",
          "ssl_country": "BR",
          "ssl_email": "william.spam@ixsystems.com",
          "ssl_org": "iXsystems",
          "ssl_state": "Parana"
}

r = requests.get(url, auth = auth)
r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
result = json.loads(r.text)
for items in result:
  print items+':', result[items]
