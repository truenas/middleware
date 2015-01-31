#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
service = 'smart'
headers = conn.headers
auth = conn.auth
payload = {
          "smart_interval": 50
}
url = conn.url + 'services/smart/' 

def get():
  print 'Getting services-smart ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-smart --> Succeeded!'
  else:
    print 'Get services-smart --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-smart --> Succeeded!'
  else:
    print 'Update services-smart --> Failed!'

def post():                                                                  
  print 'No POST function for services-smart!'

def delete():
  print 'No DELETE function for services-smart!'

