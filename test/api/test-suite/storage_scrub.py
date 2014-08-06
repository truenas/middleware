#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

#vol_name = raw_input('Input volume name:')
url = conn.url + 'storage/scrub/'
auth = conn.auth
headers = conn.headers
payload = {
          "scrub_volume": 2,
          "scrub_dayweek": "7",
          "scrub_minute": "00",
          "scrub_hour": "00",
          "scrub_month": "*",
          "scrub_daymonth": "*"
}

def scrub_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]

def scrub_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def scrub_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def scrub_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code

while (1):
  method = raw_input('Input method:')
  if method == 'get':
    scrub_get()
  elif method == 'post':
    scrub_post()
  elif method == 'delete':
    scrub_delete()
  elif method == 'put':
    scrub_put()
