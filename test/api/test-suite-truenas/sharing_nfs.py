#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os
import extra_functions

if extra_functions.volume_check() == False:
  import storage_volume
  storage_volume.post()

os.system('rm *.pyc')
headers = conn.headers
auth = conn.auth
url = conn.url + 'sharing/nfs/'
payload = {"nfs_alldirs": false, "nfs_comment": "", "nfs_hosts": "", "nfs_mapall_group": "", "nfs_mapall_user": "", "nfs_maproot_group": "", 
"nfs_maproot_user": "", "nfs_network": "", "nfs_paths": ["/mnt/new_volume_test_suite"], "nfs_quiet": false, "nfs_ro": false}
payloadd = {
	  "nfs_mapall_user": "", 
	  "nfs_maproot_group": "", 
	  "nfs_maproot_user": "", 
	  "nfs_network": "", 
	  "nfs_ro": False,
	  "nfs_hosts": "",
	  "nfs_alldirs": False,
	  "nfs_mapall_group": "", 
	  "nfs_comment": "", 
	  "nfs_quiet": False,
          "nfs_comment": "New_NFS_Share_test_suite",
          "nfs_paths": ['/mnt/new_volume_test_suite']
}

def get():
  print 'Getting sharing-nfs ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet sharing-nfs --> Succeeded!'
  else:
    print 'Get sharing-nfs --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create sharing-nfs --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create sharing-nfs --> Failed!'
    print r.text

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update sharing-nfs --> Succeeded!'
  else:
    print 'Update sharing-nfs --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete sharing-nfs --> Succeeded!'
    else:
      print 'Delete sharing-nfs --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete sharing-nfs --> Succeeded!'
    else:
      print 'Delete sharing-nfs --> Failed!'
