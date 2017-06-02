#!/usr/local/bin/python
from middlewared.client import Client
from middlewared.client.utils import Struct

import os
import pwd
import grp
import hashlib
import crypt
import random
from subprocess import Popen, PIPE
import logging

log = logging.getLogger('generate_webdav_config')


def salt():
    """
    Returns a string of 2 random letters.
    Taken from Eli Carter's htpasswd.py
    """
    letters = 'abcdefghijklmnopqrstuvwxyz' \
              'ABCDEFGHIJKLMNOPQRSTUVWXYZ' \
              '0123456789/.'
    return '$6${0}'.format(''.join([random.choice(letters) for i in range(16)]))


# The below is a function borrowed form the notifier
def _pipeopen(command):
        log.debug("Popen()ing: %s", command)
        return Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)


# The function below basically recursively changes the user and group
# ownership of an entire directory. In other words it executes the
# following: chown -r user:group dir/
# Please use this function when the depth of directory is small else
# pipeopen and then execute the abvoe command.
def _chownrecur(path, uid, gid):
    os.chown(path, uid, gid)
    for item in os.listdir(path):
        itempath = os.path.join(path, item)
        if os.path.isfile(itempath):
            os.chown(itempath, uid, gid)
        elif os.path.isdir(itempath):
            os.chown(itempath, uid, gid)
            _chownrecur(itempath, uid, gid)


def dav_passwd_change(passwd, auth_type):
    if auth_type == 'basic':
        with open("/etc/local/apache24/webdavhtbasic", "w+") as f:
            f.write("webdav:{0}".format(crypt.crypt(passwd, salt())))
    else:
        with open("/etc/local/apache24/webdavhtdigest", "w+") as f:
            f.write(
                "webdav:webdav:{0}".format(hashlib.md5(f"webdav:webdav:{passwd}".encode()).hexdigest())
            )
    os.chown(
        "/etc/local/apache24/webdavht{0}".format(auth_type),
        pwd.getpwnam("webdav").pw_uid,
        grp.getgrnam("webdav").gr_gid
    )


def main():
    """Use middleware client to generate a config file."""
    client = Client()
    # Obtain the various webdav configuration details from services object
    webby = Struct(client.call('datastore.query', 'services.WebDAV', None, {'get': True}))
    dav_tcpport = webby.webdav_tcpport
    dav_tcpportssl = webby.webdav_tcpportssl
    dav_protocol = webby.webdav_protocol
    dav_auth_type = webby.webdav_htauth
    dav_passwd = webby.webdav_password
    if dav_protocol != 'http':
        dav_ssl_certfile = '/etc/certificates/%s.crt' % webby.webdav_certssl.cert_name
        dav_ssl_keyfile = '/etc/certificates/%s.key' % webby.webdav_certssl.cert_name

    # Declaring the config file locations as well as making some
    # generic config-text blocks
    dav_config_file = '/etc/local/apache24/Includes/webdav.conf'
    davssl_config_file = '/etc/local/apache24/Includes/webdav-ssl.conf'
    dav_auth_text = ""
    if dav_auth_type == 'digest':
        dav_auth_text = "AuthDigestProvider file"
    dav_config_pretext = """
        DavLockDB "/etc/local/apache24/var/DavLock"
        AssignUserId webdav webdav

        <Directory />
          AuthType %s
          AuthName webdav
          AuthUserFile "/etc/local/apache24/webdavht%s"
          %s
          Require valid-user

          Dav On
          IndexOptions Charset=utf-8
          AddDefaultCharset UTF-8
          AllowOverride None
          Order allow,deny
          Allow from all
          Options Indexes FollowSymLinks
        </Directory>\n""" % (dav_auth_type, dav_auth_type, dav_auth_text)
    dav_config_posttext = """
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
        </VirtualHost>"""

    # Generate the webdav password files
    dav_passwd_change(dav_passwd, dav_auth_type)

    # Check to see if there is a webdav lock databse directory, if not create
    # one. Take care of necessary permissions whilst creating it!
    oscmd = "/etc/local/apache24/var"
    if not os.path.isdir(oscmd):
        os.mkdir(oscmd, 0o774)
    _chownrecur(oscmd, pwd.getpwnam("webdav").pw_uid, grp.getgrnam("webdav").gr_gid)

    # Now getting to the actual webdav share details and all
    webshares = [Struct(i) for i in client.call('datastore.query', 'sharing.WebDAV_Share')]

    if dav_protocol in ['http', 'httphttps']:
        if dav_protocol == 'http':
            with open(davssl_config_file, 'w') as f2:
                f2.write("")
        with open(dav_config_file, 'w') as f:
            f.write(" Listen " + str(dav_tcpport) + "\n")
            if webby.webdav_bindip:
                f.write(" Listen %s:80\n" % ' '.join(webby.webdav_bindip))
                f.write("\t <VirtualHost %s *:%s>\n" % (' '.join(webby.webdav_bindip), str(dav_tcpport)))
            else:
                f.write("\t <VirtualHost *:" + str(dav_tcpport) + ">\n")
            f.write("\t <VirtualHost *:" + str(dav_tcpport) + ">\n")
            f.write(dav_config_pretext)
            for share in webshares:
                temp_path = """ "%s" """ % share.webdav_path
                f.write("\t   Alias /" + share.webdav_name + temp_path + "\n")
                f.write("\t   <Directory " + temp_path + ">\n")
                f.write("\t   </Directory>\n")
                if share.webdav_ro == 1:
                        f.write(
                            "\t   <Location /" +
                            share.webdav_name +
                            ">\n\t\t AllowMethods GET OPTIONS PROPFIND\n\t   </Location>\n"
                        )
                if share.webdav_perm:
                    _pipeopen("chown -R webdav:webdav %s" % share.webdav_path)
            f.write(dav_config_posttext)

    if dav_protocol in ['https', 'httphttps']:
        if dav_protocol == 'https':
            with open(dav_config_file, 'w') as f:
                f.write("")
        with open(davssl_config_file, 'w') as f2:
            f2.write(" Listen " +
                     str(dav_tcpportssl) + "\n")
            f2.write("\t <VirtualHost *:" + str(dav_tcpportssl) + ">\n")
            f2.write("\t  SSLEngine on\n")
            f2.write("""\t  SSLCertificateFile "%s"\n""" % dav_ssl_certfile)
            f2.write("""\t  SSLCertificateKeyFile "%s"\n""" % dav_ssl_keyfile)
            f2.write("\t  SSLProtocol +TLSv1 +TLSv1.1 +TLSv1.2\n\t  SSLCipherSuite HIGH:MEDIUM\n")
            f2.write(dav_config_pretext)
            # Note: The for loop below is essentially code duplication,
            # but since two different files are being written to I could
            # not at the moment find a more efficient way of doing this.
            # (if you can fix it, please do so)
            for share in webshares:
                temp_path = """ "%s" """ % share.webdav_path
                f2.write("\t   Alias /" + share.webdav_name + temp_path + "\n")
                f2.write("\t   <Directory " + temp_path + ">\n")
                f2.write("\t   </Directory>\n")
                if share.webdav_ro == 1:
                    f2.write(
                        "\t   <Location /" +
                        share.webdav_name +
                        ">\n\t\t AllowMethods GET OPTIONS PROPFIND\n\t   </Location>\n"
                    )
                # Note: the 'and' in the if statement below is to ensure
                # that we do not waste time in changin permisions twice
                # (once while in http block)
                if (share.webdav_perm and dav_protocol != "httphttps"):
                    _pipeopen("chown -R webdav:webdav %s" % share.webdav_path)
            f2.write(dav_config_posttext)

if __name__ == "__main__":
    main()
