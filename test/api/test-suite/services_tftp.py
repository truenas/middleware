#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os
import extra_functions

os.system('rm *.pyc')
headers = conn.headers
auth = conn.auth
payload = {
          "tftp_port": 75,
          "tftp_directory": "/mnt/new_volume_test_suite"
}
url = conn.url + 'services/tftp/' 

def get():
  print 'Getting services-tftp ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-tftp --> Succeeded!'
  else:
    print 'Get services-tftp --> Failed!'
  
def put():
  if extra_functions.volume_check() == False:
    import storage_volume
    storage_volume.post()
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-tftp --> Succeeded!'
  else:
    print 'Update services-tftp --> Failed!'

def post():                                                                  
  print 'No POST function for services-tftp!'

def delete():
  print 'No DELETE function for services-tftp!'

