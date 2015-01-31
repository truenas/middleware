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
          "ups_rmonitor": "true",
          "ups_port":"/dev/ugen0.1"
}
url = conn.url + 'services/ups/' 

def get():
  print 'Getting services-ups ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-ups --> Succeeded!'
  else:
    print 'Get services-ups --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-ups --> Succeeded!'
  else:
    print 'Update services-ups --> Failed!'

def post():                                                                  
  print 'No POST function for services-ups!'

def delete():
  print 'No DELETE function for services-ups!'

