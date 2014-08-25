#!/usr/local/bin/python

import requests
import json
import sys
import conn

auth = conn.auth
headers = conn.headers
url = conn.url + 'plugins/plugins/'

def get():
  print 'Getting plugins ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet plugins --> Succeeded!'
  else:
    print 'Get plugins --> Failed!'

def start():
  print 'Starting plugins ......'
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) != 0:
    id = get_id()+'/start/'
    r = requests.post(url+id, auth = auth)
    if r.stuatus_code == 200:
      print 'Plugin started --> Succeeded!'
    else:
      print 'Plugin failed to start --> Failed!'
  else:
    print 'No plugins founded'

def stop():
  print 'Stopping plugins ......'
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) != 0:
    id = get_id()+'/stop/'
    r = requests.post(url+id, auth = auth)
    if r.stuatus_code == 200:
      print 'Plugin stopped --> Succeeded!'
    else:
      print 'Plugin failed to stop --> Failed!'
  else:
    print 'No plugins founded'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) != 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete plugins --> Succeeded!'
    else:
      print 'Delete plugins --> Failed!'
  else:
    print 'No plugins founded'

def get_id():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  id = str(result[0]['id'])
  return id

def operating():
  print '\n***Running Plugins-Start ......'
  start()
  print ''

  print '***Running Plugins-Stop ......'
  stop()
  print ''

  print '***Running Plugins-Delete ......'
  delete()
  print '\n'


def main():
  print '******WARNING******'
  warn = raw_input('This operation will destory everything in Plugins(yes/no):')
  oper_flag = 1
  while(oper_flag <= 3):
    if oper_flag == 3:
      print 'Please re-run Plugins test suite!'
      sys.exit(0)
    if warn == 'no' or warn == 'n':
      sys.exit(0)
    elif warn == 'yes' or warn == 'y':
      break
    elif warn !='no' and warn != 'yes' and warn != 'y' and warn !='n':
      warn = raw_input("Invalid operation! Please input 'yes' or 'no':")
      oper_flag = oper_flag + 1
      continue

  operating()


if __name__ == '__main__':
  main()
