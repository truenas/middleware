#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
service = 'snmp'
headers = conn.headers
auth = conn.auth
payload = {
          "snmp_contact": "admin@freenas.org",
          "snmp_traps": False
}
url = conn.url + 'services/snmp/' 

def get():
  print 'Getting services-snmp ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-snmp --> Succeeded!'
  else:
    print 'Get services-snmp --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-snmp --> Succeeded!'
  else:
    print 'Update services-snmp --> Failed!'

def post():                                                                  
  print 'No POST function for services-snmp!'

def delete():
  print 'No DELETE function for services-snmp!'
