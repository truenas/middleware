#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
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

def put():
  r = requests.put(url, auth = auth, headers = headers, data = json.dumps(payload))
  if r.status_code == 200:
    result = json.loads(r.text)
    print 'Update system-ssl --> Succeeded!'
  else:
    print 'Update system-ssl --> Failed!'

def get():
  print 'Getting system-ssl ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items+':', result[items]
    print 'Get system-ssl --> Succeeded!'
  else:
    print 'Get system-ssl --> Failed!'

def post():
  print 'No POST function for system-ssl!'

def delete():
  print 'No DELETE function for system-ssl!'
