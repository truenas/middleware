#!/usr/local/bin/python

import requests
import json

# BASIC REQUESTS INFO
url = 'http://freenas-test1.sjlab1.ixsystems.com/api/v1.0/'
headers = {'Content-Type':'application/json'}

# GET VOLUME INFORMATION
def get_vol_info():
  r = requests.get(url+'/storage/volume/',auth=authen)
  vollist = json.loads(r.text)
  i = 0
  for i in range(0,len(vollist)):
    print '\n'
    for items in vollist[i]:
      print items+':',vollist[i][items]
  if r.status_code != 200:
    print 'Error information:\n'+r.text
  return r.status_code
  
# DELETE VOLUME
def delete_vol():
  volid = raw_input('Input the id of volume you want to delete:')
  r = requests.delete(url+'/storage/volume/'+'/'+volid+'/',auth=authen)
  if r.status_code != 204:
    print 'Error information:\n'+r.text
  return r.status_code

# CREATE NEW VOLUME
def create_vol():
  # VOLUME NAME
  volname = raw_input('Input volume name:')

  # VDETYPE
  vdetypelist = ['stripe', 'mirror', 'raidz', 'raidz2', 'raidz3']
  while (1):
    vdetype = raw_input('Input vdetype(stripe, mirror, raidz, raidz2, raidz3):')
    if (vdetype not in vdetypelist):
      print 'Input a right vdetype!\n'
      continue
    else:
      break
  
    # DISKS
  print '\nAvailable disks:'
  r = requests.get(url+'/storage/disk/',auth=authen)
  i = 0
  disklist_known = []
  disklist = json.loads(r.text)
        
  for item in disklist:
    disk = disklist[i]['disk_name']
    print disk
    i = i+1
    disklist_known.append(disk)
  
  disks = []
  j = 1
  print "Input 'stop' when finished inputting disks!\n"
  while(j < len(disklist)+1):
    disk = raw_input('Input the #' + str(j) + ' disk:')
    if disk == 'stop':
      print 'Finished inputting disks!\n'
      break
    if (disk not in disklist_known):
      print 'Wrong disk name!\n'
      continue
    j = j + 1
    disks.append(disk)
    
  # REQUEST
  payload = {
          'volume_name': volname,
          'layout': [
                  {
                          'vdevtype': vdetype,
                          'disks': disks
                  }
          ]
  }
  r = requests.post(url+'/storage/volume/',auth=authen,data=json.dumps(payload),headers=headers)
  print 'New volume information:\n'
  newvol = json.loads(r.text)
  for items in newvol:
    print items+':',newvol[items]
  return r.status_code

# GET USERS INFORMATION
def get_user_info():
  r = requests.get(url+'/account/users/', auth=authen)
  print 'Users information:\n',r.text

  user_info = json.loads(r.text)
  i = 0
  for i in range(0,len(user_info)):
    print '\n'
    for items in user_info[i]:
      print items+':',user_info[i][items]
  if r.status_code != 200:
    print 'Error information:\n'+r.text
  return r.status_code
  
# CHANGE PASSWORD OF USERS
def change_user_passwd():
  r = requests.get(url+'/account/users/', auth=authen)
  userlist = json.loads(r.text)

  print '----------------'
  print '|','id','|','user_name'
  print '----------------'
  i = 0
  bsdusr_id_known = []
  for item in userlist:
    bsdusr_name = userlist[i]['bsdusr_username']
    bsdusr_id = userlist[i]['id']
    bsdusr_id_known.append(str(bsdusr_id))
    if bsdusr_id < 10:
      bsdusr_id = ' '+str(bsdusr_id)
    print '|',bsdusr_id,'|',bsdusr_name
    i = i+1
  print '----------------'
  while(1):
    user_id = raw_input('Input id of user you want to change its password:')
    if user_id not in bsdusr_id_known:
      print 'Wrong user id!'
      continue
    else:
      break
  
  new_passwd = raw_input('Input new password:')
  payload = {
        'bsdusr_password': new_passwd
  }
  r = requests.post(url+'/account/users/'+user_id+'/password/', auth=authen, data=json.dumps(payload), headers=headers)
  status_code = r.status_code
    
  if r.status_code != 200:
    print 'Password unsuccessfully changed!\n'+'Error information:\n'+r.text
  print '\nPlease relogin:'
    
def create_dataset():
  return 0

# AUTHENTICATION
username = ''
passwd = ''
while(1):
  while(username == '' and passwd == ''):    
    username = raw_input('Username:')
    passwd = raw_input('password:')
    authen = (username,passwd)
    r = requests.get(url+'/account/users/',auth=authen)
    if r.status_code == 401:
      print 'Wrong username/password!\n'
      username = ''
      passwd = ''
      continue
    else:
      print 'Authentication succeeded!\n' 
      break

#Operations on volume:
  print "1: Get info of volumes\n2: Delete volume\n3: Create a new volume\n4: Get info of users\n5: Change password\n6: Create a new dataset in volume\n"

  operation = raw_input('Input operation #:')
  
  
  # GET INFO OF VOLUMES
  if operation == '1':
    status_code = get_vol_info()

  # DELETE VOLUME
  elif operation == '2':
    status_code = delete_vol()

  # CREATE NEW VOLUME
  elif operation == '3':
    status_code = create_vol() 

  # GET USERS INFO
  elif operation == '4':
    status_code = get_user_info()

  # CHANGE PASSOWRD OF USERS
  elif operation == '5':
    status_code = change_user_passwd()
    username = ''
    passwd = ''
    continue
  elif operation == '6':
    status_code = create_dataset()

  # WRONG INPUT  
  else:
    print 'Worong Input!'
    continue

  #STATUS CHECK:
  if status_code == 200:
    if operation == '1':
      print 'Succeeded getting volume infomation!\n'
      print "*Volume infomation:('[]'if there is no volume)\n"
    if operation == '4':
      print 'Succeeded getting user information!\n'
    if operation == '5':
      print 'Password succeddfully changed!\n'
  elif status_code == 204 and operation == '2':
    print 'Succeeded deleted volume !\n'
  elif status_code == 201 and operation == '3':
    print 'Succeed created new volume !\n'
  elif status_code == 404 and operation == '2':
    print 'Volume not found, input 1 to recheck volume id!\n'
  elif status_code == 0:
    print "API info missing on 'http://api.freenas.org/'\n"

