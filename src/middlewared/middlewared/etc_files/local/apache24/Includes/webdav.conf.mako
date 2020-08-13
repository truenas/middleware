<%
	import crypt
	import hashlib
	import itertools
	import os
	import random
	import subprocess

	from string import digits, ascii_uppercase, ascii_lowercase
	from middlewared.utils import osc

	# Check to see if there is a webdav lock databse directory, if not create
	# one. Take care of necessary permissions whilst creating it!
	apache_dir = service.APACHE_DIR
	if osc.IS_LINUX:
		apache_dir = apache_dir.replace('local/', '')
	oscmd = f'/etc/{apache_dir}/var'
	if not os.path.isdir(oscmd):
		os.mkdir(oscmd, 0o774)

	try:
		uid = middleware.call_sync('user.get_user_obj', {'username': 'webdav'})['pw_uid']
		gid = middleware.call_sync('group.get_group_obj', {'groupname': 'webdav'})['gr_gid']
	except Exception:
		uid = 0
		gid = 0

	subprocess.run(['chown', '-R', f'{uid}:{gid}', oscmd], check=False)

	webdav_config = middleware.call_sync('webdav.config')
	auth_type = webdav_config['htauth'].lower()
	web_shares = middleware.call_sync('sharing.webdav.query', [['enabled', '=', True]])
	password = webdav_config["password"]

	# Generating relevant password files

	def salt():
		"""
		Returns a string of 2 random letters.
		Taken from Eli Carter's htpasswd.py
		"""
		letters = f'{ascii_lowercase}{ascii_uppercase}{digits}/.'
		return '$6${0}'.format(''.join([random.choice(letters) for i in range(16)]))

	if auth_type == 'none':
		path = None
	elif auth_type == 'basic':
		path = f'/etc/{apache_dir}/webdavhtbasic'
		with open(path, 'w+') as f:
			f.write(f'webdav:{crypt.crypt(password, salt())}')
	elif auth_type == 'digest':
		path = f'/etc/{apache_dir}/webdavhtdigest'
		with open(path, 'w+') as f:
			f.write(
				"webdav:webdav:{0}".format(hashlib.md5(f"webdav:webdav:{password}".encode()).hexdigest())
			)
	else:
		raise ValueError("Invalid auth_type (must be one of 'none', 'basic', 'digest')")

	if path:
		os.chown(path, uid, gid)

%>\
Listen ${webdav_config['tcpport']}
	<VirtualHost *:${webdav_config['tcpport']}>
		DavLockDB "/etc/${apache_dir}/var/DavLock"
		AssignUserId webdav webdav

		<Directory />
% if auth_type != 'none':
			AuthType ${auth_type}
			AuthName webdav
			AuthUserFile "/etc/${apache_dir}/webdavht${auth_type}"
	% if auth_type == 'digest':
			AuthDigestProvider file
	% endif
			Require valid-user

% endif
			Dav On
			IndexOptions Charset=utf-8
			AddDefaultCharset UTF-8
			AllowOverride None
			Order allow,deny
			Allow from all
			Options Indexes FollowSymLinks
		</Directory>

% for share in web_shares:
	<%
		if share['locked']:
			middleware.logger.debug(
			    'Skipping generation of %r webdav share as underlying resource is locked', share['name']
			)
			middleware.call_sync('sharing.webdav.generate_locked_alert', share['id'])
			continue
	%>\
		Alias /${share['name']} "${share['path']}"
		<Directory "${share['path']}" >
		</Directory>
	% if share['ro']:
		<Location "/${share['name']}" >
			AllowMethods GET OPTIONS PROPFIND
		</Location>
	% endif

% endfor
		# The following directives disable redirects on non-GET requests for
		# a directory that does not include the trailing slash.  This fixes a
		# problem with several clients that do not appropriately handle
		# redirects for folders with DAV methods.
		BrowserMatch "Microsoft Data Access Internet Publishing Provider" redirect-carefully
		BrowserMatch "MS FrontPage" redirect-carefully
		BrowserMatch "^WebDrive" redirect-carefully
		BrowserMatch "^WebDAVFS/1.[01234]" redirect-carefully
		BrowserMatch "^gnome-vfs/1.0" redirect-carefully
		BrowserMatch "^XML Spy" redirect-carefully
		BrowserMatch "^Dreamweaver-WebDAV-SCM1" redirect-carefully
		BrowserMatch " Konqueror/4" redirect-carefully
		RequestReadTimeout handshake=0 header=20-40,MinRate=500 body=20,MinRate=500
	</VirtualHost>
