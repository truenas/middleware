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
          "ldap_hostname": "ldaphostname",
          "ldap_basedn": "dc=test,dc=org"
}
url = conn.url + 'directoryservice/ldap/' 

def get():
  print 'Getting directoryservice-nis ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get directoryservice-nis --> Succeeded!'
  else:
    print 'Get directoryservice-nis --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update directoryservice-nis --> Succeeded!'
  else:
    print 'Update directoryservice-nis --> Failed!'

def post():                                                                  
  print 'No POST function for directoryservice-nis!'

def delete():
  print 'No DELETE function for directoryservice-nis!'

