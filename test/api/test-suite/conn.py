import json

f = file('server.config')
info = json.load(f)
username = info['username']
password = info['password']
auth = (username,password)
headers = {'Content-Type':'application/json'}
url = "http://%s/api/v1.0/" % info['hostname']
f.close()
