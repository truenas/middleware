#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
headers = conn.headers
auth = conn.auth
payload = {
          "ddns_provider": "dyndns@dyndns.org"
}
url = conn.url + 'services/dynamicdns/'

def get():
  print 'Getting services-dynamicdns ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-dynamicdns --> Succeeded!'
  else:
    print 'Get services-dynamicdns --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-dynamicdns --> Succeeded!'
  else:
    print 'Update services-dynamicdns --> Failed!'

def post():                                                                  
  print 'No POST function for services-dynamicdns!'

def delete():
  print 'No DELETE function for services-dynamicdns!'


