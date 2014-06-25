import requests

while(1):
  user_name = raw_input('Username: ')
  user_passwd = raw_input('Password: ')
  url = 'http://freenas-test1.sjlab1.ixsystems.com/api/v1.0/'
  auth = (user_name,user_passwd)
  headers = {'Content-Type':'application/json'}
  r = requests.get(url+'/account/users/',auth=auth)
  if r.status_code == 401:
    print 'Wrong username/password!\n'
    username = ''
    passwd = ''
    continue
  else:
    print 'Authentication succeeded!\n'
    break

