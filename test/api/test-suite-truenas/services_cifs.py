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
          "cifs_srv_hostlookup": "false",
          "cifs_srv_bindip": []

}
url = conn.url + 'services/cifs/' 

def get():
  print 'Getting services-cifs ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-cifs --> Succeeded!'
  else:
    print 'Get services-cifs --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
#  print r.status_code
#  print r.text
  if r.status_code == 200:
    print 'Update services-cifs --> Succeeded!'
  else:
    print 'Update services-cifs --> Failed!'

def post():                                                                  
  print 'No POST function for services-cifs!'

def delete():
  print 'No DELETE function for services-cifs!'


