#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
auth = conn.auth
url = conn.url + 'system/cronjob/'
payload = {
          "cron_user": "root",
          "cron_command": "/data/myscript.sh",
          "cron_minute": "*/20",
          "cron_hour": "*",
          "cron_daymonth": "*",
          "cron_month": "*",
          "cron_dayweek": "*"
}

def cronjob_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def cronjob_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def cronjob_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items] 

def cronjob_delete():
  id = raw_input('Input id:')+'/' 
  r = requests.delete(url+id, auth = auth) 
  print r.status_code

def cronjob_run():
  id = raw_input('Input id:')+'/'
  r = requests.post(url+id+'run/', auth = auth)
  print r.text

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    cronjob_get()
  elif method == 'post':
    cronjob_post()
  elif method == 'put':
    cronjob_put()
  elif method == 'delete':
    cronjob_delete() 
  elif method == 'run':
    cronjob_run()
