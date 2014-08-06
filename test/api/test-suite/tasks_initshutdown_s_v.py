#!/usr/local/bin/python

import requests
import json
import sys
import conn

headers = conn.headers
auth = conn.auth
url = conn.url + 'tasks/initshutdown/'
payload = {
          "ini_type": "command",
          "ini_command": "rm /mnt/tank/temp*",
          "ini_when": "postinit"
}

def get():
  print 'Getting tasks-initshudown ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print '\n'
      for items in result[i]:
        print items+':', result[i][items]
    print 'Get tasks-initshudown --> Succeeded!'
  else:
    print 'Get tasks-initshudown --> Failed!'

def post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create tasks-initshudown --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create tasks-initshudown --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update tasks-initshudown --> Succeeded!'
  else:
    print 'Update tasks-initshudown --> Failed!'

def delete():
  id = post()
  r = requests.delete(url+id, auth = auth)
  if r.status_code == 204:
    print 'Delete tasks-initshudown --> Succeeded!'
  else:
    print 'Delete tasks-initshudown --> Failed!'

