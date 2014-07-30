#!/usr/local/bin/python

import requests
import json
import sys
import conn
import storage_disk

headers = conn.headers
auth = conn.auth
url = conn.url + 'storage/volume/'
disk_name = storage_disk.get()
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

def post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create storage-volume --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create storage-volume --> Failed!'

def put():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result)>0:
    r = requests.put(url+'1/', auth = auth, data = json.dumps(payload), headers = headers)
  else:                                                                   
    id = post()
    r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update storage-volume --> Succeeded!'
  else:
    print 'Update storage-volume --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result)>0:
    r = requests.delete(url+'1/', auth = auth)
  else:
    id = post()
    r = requests.delete(url+id, auth = auth)
  if r.status_code == 204:
    print 'Delete storage-volume --> Succeeded!'
  else:
    print 'Delete storage-volume --> Failed!'
