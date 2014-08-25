#!/usr/local/bin/python

import requests
import json
import sys 
import conn
import os

os.system('rm *.pyc')
url = conn.url + 'network/lagg/'
auth = conn.auth
headers = conn.headers
payload = {
          "lagg_interfaces": ["em0"],
          "lagg_protocol": "roundrobin"
}

def get():
  print 'Getting network-lagg ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet network-lagg --> Succeeded!'
  else:
    print 'Get network-lagg --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create network-lagg --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create network-lagg --> Failed!'

def put():
  print 'No PUT function for network-lagg!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete network-lagg --> Succeeded!'
    else:
      print 'Delete network-lagg --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete network-lagg --> Succeeded!'
    else:
      print 'Delete network-lagg --> Failed!'
