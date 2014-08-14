#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
headers = conn.headers
auth = conn.auth
url = conn.url + 'storage/disk/'
payload = {
          "disk_description": "newdescription"
}


def get():
  print 'Getting storage-disk ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet storage-disk --> Succeeded!'
  else:
    print 'Get storage-disk --> Failed!'

def put():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result)>0:
    r = requests.put(url+str(result[0]['id'])+'/', auth = auth, data = json.dumps(payload), headers = headers)
    if r.status_code == 200:
      print 'Update storage-disk --> Succeeded!'
    else:
      print 'Update storage-disk --> Failed!'
      print r.text

def post():
  print 'No POST function for storage-disk!'

def delete():
  print 'No DELETE function for storage-disk!'
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  


def get_name():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  return result[0]['disk_name']

def get_id():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  return result[0]['id']
