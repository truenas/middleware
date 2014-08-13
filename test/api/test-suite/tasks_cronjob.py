#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
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
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet tasks-cronjob --> Succeeded!'
  else:
    print 'Get tasks-cronjob --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create tasks-cronjob --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create tasks-cronjob --> Failed!'
    return ''

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update tasks-cronjob --> Succeeded!'
  else:
    print 'Update tasks-cronjob --> Failed!'

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

def run():
  id = post()
  r = requests.post(url+id+'run/', auth = auth)
  if r.status_code == 202:
    print 'Cronjob is running ...... --> Succeeded!'
  else:
    print 'Cronjob is not running --> Failed!'

