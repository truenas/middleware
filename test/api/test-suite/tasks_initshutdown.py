#!/usr/local/bin/python

import requests
import json
import sys
import os
import conn
import extra_functions
import storage_volume

os.system('rm *.pyc')
if extra_functions.volume_check() == False:
  storage_volume.post()

headers = conn.headers
auth = conn.auth
url = conn.url + 'tasks/initshutdown/'
payload = {
          "ini_type": "command",
          "ini_command": "rm /mnt/new_volume_test_suite/temp*",
          "ini_when": "postinit"
}

def get():
  print 'Getting tasks-initshutdown ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet tasks-initshutdown --> Succeeded!'
  else:
    print 'Get tasks-initshutdown --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create tasks-initshutdown --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create tasks-initshutdown --> Failed!'
    return ''

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update tasks-initshutdown --> Succeeded!'
  else:
    print 'Update tasks-initshutdown --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete tasks-initshutdown --> Succeeded!'
    else:
      print 'Delete tasks-initshutdown --> Failed!'
  if len(result) == 0:
    id = post() 
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete tasks-initshutdown --> Succeeded!'
    else:
      print 'Delete tasks-initshutdown --> Failed!'
