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
          "ad_netbiosname": "mynas",
          "ad_domainname": "example.com",
          "ad_bindname": "admin",
          "ad_bindpw": "mypw"
}
url = conn.url + 'directoryservice/activedirectory/' 

def get():
  print 'Getting directoryservice-activedirectory ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get directoryservice-activedirectory --> Succeeded!'
  else:
    print 'Get directoryservice-activedirectory --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update directoryservice-activedirectory --> Succeeded!'
  else:
    print 'Update directoryservice-activedirectory --> Failed!'

def post():                                                                  
  print 'No POST function for directoryservice-activedirectory!'

def delete():
  print 'No DELETE function for directoryservice-activedirectory!'

