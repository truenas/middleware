#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
auth = conn.auth
url = conn.url + 'system/alert/'

def get():
  print 'Getting system-alert ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      for items in result[i]:
        print items+':', result[i][items]
    print 'Get system-alert --> Succeeded!'
  else:
    print 'Get system-alert --> Failed!'

def put():
  print 'No PUT function for system-alert!'

def post():
  print 'No POST function for system-alert!'

def delete():
  print 'No DELETE function for system-alert!'
