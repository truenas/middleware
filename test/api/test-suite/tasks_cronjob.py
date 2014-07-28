#!/usr/local/bin/python

import requests
import json
import sys
import conn

headers = conn.headers
auth = conn.auth
url = conn.url + 'tasks/cronjob/'
payload = {
          "cron_user": "root",
          "cron_command": "/data/myscript.sh",
          "cron_minute": "*/20",
          "cron_hour": "*",
          "cron_daymonth": "*",
          "cron_month": "*",
          "cron_dayweek": "*"
}


def get():
  print 'Getting tasks-cronjob ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print '\n'
      for items in result[i]:
        print items+':', result[i][items]
    print 'Get tasks-cronjob --> Succeeded!'
  else:
    print 'Get tasks-cronjob --> Failed!'

def post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create tasks-cronjob --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create tasks-cronjob --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update tasks-cronjob --> Succeeded!'
  else:
    print 'Update tasks-cronjob --> Failed!'

def delete():
  id = post()
  r = requests.delete(url+id, auth = auth)
  if r.status_code == 204:
    print 'Delete tasks-cronjob --> Succeeded!'
  else:
    print 'Delete tasks-cronjob --> Failed!'

def run():
  id = post()
  r = requests.post(url+id+'run/', auth = auth)
  if r.status_code == 202:
    print 'Cronjob is running ...... --> Succeeded!'
  else:
    print 'Cronjob is not running --> Failed!'

