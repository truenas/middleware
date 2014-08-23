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
          "lldp_intdesc": "false"
}
url = conn.url + 'services/lldp/' 

def get():
  print 'Getting services-lldp ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-lldp --> Succeeded!'
  else:
    print 'Get services-lldp --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-lldp --> Succeeded!'
  else:
    print 'Update services-lldp --> Failed!'

def post():                                                                  
  print 'No POST function for services-lldp!'

def delete():
  print 'No DELETE function for services-lldp!'


