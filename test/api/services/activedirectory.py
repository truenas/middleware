#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'activedirectory'
headers = conn.headers
auth = conn.auth
payload = {
          "ad_netbiosname": "mynas",
          "ad_domainname": "mydomain",
          "ad_adminname": "admin",
          "ad_adminpw": "mypw",
          "ad_bindname" :"",
          "ad_workgroup" : "",
          "ad_bindpw" : ""

}
url = conn.url + 'services/' + service + '/' 

#r = requests.get(url, auth = auth)
r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)

result = json.loads(r.text)
for items in result:
  print items,':',result[items]


