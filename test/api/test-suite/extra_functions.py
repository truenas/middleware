import json
import requests
import conn

url = conn.url
auth = conn.auth
headers = conn.headers

def volume_check():
  vol_list = []
  vol_name = 'new_volume_test_suite'
  r = requests.get(url+'storage/volume/', auth = auth)
  result = json.loads(r.text)
  i = 0
  if len(result)>0:
    for i in range(0,len(result)):
      vol_list.append(result[i]['vol_name'])
  if vol_name in vol_list:
    return True
  else:
    return False

def task_check():
  task_list = []
  task_filesystem = 'new_volume_test_suite'
  r = requests.get(url+'storage/task/', auth = auth)
  result = json.loads(r.text)
  i = 0
  if len(result)>0:
    for i in range(0,len(result)):
      task_list.append(result[i]['task_filesystem'])
  if task_filesystem in task_list:
    return True
  else:
    return False


def volume_exist_check():
  r = requests.get(url+'storage/volume/', auth = auth)
  result = json.loads(r.text)
  return result
