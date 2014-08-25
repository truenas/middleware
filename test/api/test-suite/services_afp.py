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
          "afp_srv_guest": True,
          "afp_srv_connections_limit": 60
}
url = conn.url + 'services/afp/' 

def get():
  print 'Getting services-afp ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-afp --> Succeeded!'
  else:
    print 'Get services-afp --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-afp --> Succeeded!'
  else:
    print 'Update services-afp --> Failed!'

def post():                                                                  
  print 'No POST function for services-afp!'

def delete():
  print 'No DELETE function for services-afp!'
