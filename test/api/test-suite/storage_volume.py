#!/usr/local/bin/python

import requests
import json
import sys
import conn
import storage_disk

headers = conn.headers
auth = conn.auth
url = conn.url + 'storage/volume/'
disk_name = storage_disk.get_name()
payload = {
          "volume_name": "new_volume_test_suite",
          "layout": [
                  {
                          "vdevtype": "stripe",
                          "disks": [disk_name]
                  }
          ]
}


def get():
  print 'Getting storage-volume ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print '\n'
      for items in result[i]:
        print items+':', result[i][items]
    print 'Get storage-volume --> Succeeded!'
  else:
    print 'Get storage-volume --> Failed!'
  return r

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  if len(result)>0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create storage-volume --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create storage-volume --> Failed!'

def put():
  print 'No PUT function for storage-volume!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result)>0:
    for i in range(0,len(result)):
      r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
      if r.status_code == 204:
        print 'Delete storage-volume --> Succeeded!'
      else:
        print 'Delete storage-volume --> Failed!'
  else:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete storage-volume --> Succeeded!'
    else:
      print 'Delete storage-volume --> Failed!'
