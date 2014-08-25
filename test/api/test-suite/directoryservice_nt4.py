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
          "nt4_adminname": "admin",
          "nt4_dcname": "mydcname",
          "nt4_workgroup": "WORKGROUP",
          "nt4_netbiosname": "netbios",
          "nt4_adminpw": "mypw"
}
url = conn.url + 'directoryservice/nt4/' 

def get():
  print 'Getting directoryservice-nt4 ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get directoryservice-nt4 --> Succeeded!'
  else:
    print 'Get directoryservice-nt4 --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update directoryservice-nt4 --> Succeeded!'
  else:
    print 'Update directoryservice-nt4 --> Failed!'

def post():                                                                  
  print 'No POST function for directoryservice-nt4!'

def delete():
  print 'No DELETE function for directoryservice-nt4!'

