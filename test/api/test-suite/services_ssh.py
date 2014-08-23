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
          "ssh_rootlogin": True,
          "ssh_compression": False
}
url = conn.url + 'services/ssh/' 

def get():
  print 'Getting services-ssh ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-ssh --> Succeeded!'
  else:
    print 'Get services-ssh --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-ssh --> Succeeded!'
  else:
    print 'Update services-ssh --> Failed!'

def post():                                                                  
  print 'No POST function for services-ssh!'

def delete():
  print 'No DELETE function for services-ssh!'
