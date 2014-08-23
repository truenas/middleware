#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
headers = conn.headers
auth = conn.auth
payload = {
          "dc_forest_level": "2008",
	  "dc_dns_forwarder": "192.168.1.1",
	  "dc_domain": "services_realm_test_suite",
	  "dc_kerberos_realm": "",
	  "dc_passwd": "new_dcpasswd_test_suite",
	  "dc_realm": "new_realm_test_suite.org"
}
url = conn.url + 'services/domaincontroller/' 

def get():
  print 'Getting services-domaincontroller ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    for items in result:
      print items,':',result[items]
    print 'Get services-domaincontroller --> Succeeded!'
  else:
    print 'Get services-domaincontroller --> Failed!'
  
def put():
  r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-domaincontroller --> Succeeded!'
  else:
    print 'Update services-domaincontroller --> Failed!'

def post():                                                                  
  print 'No POST function for services-domaincontroller!'

def delete():
  print 'No DELETE function for services-domaincontroller!'

