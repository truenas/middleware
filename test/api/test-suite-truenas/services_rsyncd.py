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
          "rsyncd_auxiliary": "",
          "rsyncd_port": 873
}
url = conn.url + 'services/rsyncd/'

def get():
  print 'Getting services-rsyncd ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-rsyncd --> Succeeded!'
  else:
    print 'Get services-rsyncd --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-rsyncd --> Succeeded!'
  else:
    print 'Update services-rsyncd --> Failed!'


def post():
  print 'No POST function for services-rsyncd!'

def delete():
  print 'No DELETE function for services-rsyncd!'

