#!/usr/local/bin/python

import requests
import json
import sys
#sys.path.append('conn/')
#import conn

# Global var
api_url = ''
username = ''
password = ''
hostname = ''

# Operation Authorization
warn = raw_input('******Warning******This operation will destory everything on your FreeNAS system and set default configuration on it. Contiune?(yes/no):')
while(1):
  if warn == 'no' or warn == 'n':
    sys.exit(0)
  elif warn == 'yes' or warn == 'y':
    break
  elif warn !='no' and warn != 'yes' and warn != 'y' and warn !='n':
    warn = raw_input("Invalid operation! Please input 'yes' or 'no':")
    continue

# Requests Information
headers = {"Content-Type":"application/json"}


#Methods
def re_get(api_url):
  r = requests.get(url + api_url, auth = auth)
  return r

def re_get(api_url,timeout):
  try:
    r = requests.get(url + api_url, auth = auth, timeout = timeout)
    return r
  except:
    print 'Can not connect to Host: please check Network and Hostname!'
    sys.exit(0)
                                                                         
def re_post(api_url, data):
  r = requests.post(url + api_url, auth = auth, headers = headers, data = json.dumps(data))

def re_put(api_url, data):
  r = requests.put(url + api_url, auth = auth, headers = headers, data = json.dumps(data))

def re_delete(api_url):
  r = requests.post(url + api_url, auth = auth)

# Authentication
auth_flag = 1
while (auth_flag <= 3):
  hostname = raw_input('Input Hostname:')
  username = raw_input('Username:')
  password = raw_input('Password:')
  auth = (username, password)
  url = 'http://' + hostname + '/api/v1.0/'
  headers = {"Content-Type":"application/json"}
  print re_get('account/users/',10)
  if re_get('account/users/',10).status_code == 401:
    auth_flag = auth_flag + 1
    print 'Authentication failed! Please recheck Hosename, Username and Password!'
  else: 
    print 'Authentication succeed!'
    break

