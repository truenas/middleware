#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')


url = conn.url + 'network/globalconfiguration/'
auth = conn.auth
headers = conn.headers
payload = {
          "gc_domain": "local",
          "gc_hostname": "freenas",
}

def get():
  print 'Getting network-globalconfiguration ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get network-globalconfiguration --> Succeeded!'
  else:
    print 'Get network-globalconfiguration --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update network-globalconfiguration --> Succeeded!'
  else:
    print 'Update network-globalconfiguration --> Failed!'

def post():                                                                  
  print 'No POST function for network-globalconfiguration!'

def delete():
  print 'No DELETE function for network-globalconfiguration!'
