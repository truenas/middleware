#
# Copyright 2010 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################


import shutil
import os
import configparser
import subprocess
import time
from contextlib import closing
from subprocess import Popen, PIPE
from django.conf import settings
from Crypto.Cipher import DES
from zipfile import ZipFile


def vcp_enabled():
    try:
        for file in os.listdir(settings.STATIC_ROOT):
            if 'plugin' in file and '.zip' in file:
                return True
        return False
    except:
        return False


def get_management_ips():
    from django.db.models import Q
    from freenasUI.network.models import Interfaces
    qs = Interfaces.objects.all().exclude(Q(int_vip=None) | Q(int_vip=''))
    vips = [str(i.int_vip) for i in qs]
    p1 = Popen(["ifconfig", "-lu"], stdin=PIPE, stdout=PIPE, encoding='utf8')
    p1.wait()
    int_list = p1.communicate()[0].split('\n')[0].split(' ')
    int_list = [y for y in int_list if y not in (
        'lo0',
        'pfsync0',
        'pflog0',
    )]
    str_IP = []
    str_IP.append('--Select--')
    ifaces = {}
    for iface in int_list:

        ifaces[iface] = {'v4': [], 'v6': []}
        p1 = Popen(["ifconfig", iface, "inet"], stdin=PIPE, stdout=PIPE)
        p2 = Popen(["grep", "inet "], stdin=p1.stdout, stdout=PIPE, encoding='utf8')
        output = p2.communicate()[0]
        if p2.returncode == 0:
            for line in output.split('\n'):
                if not line:
                    continue
                line = line.strip('\t').strip().split(' ')
                netmask = line[3]
                try:
                    netmask = int(netmask, 16)
                    count = 0
                    for i in range(32):
                        if netmask == 0:
                            break
                        count += 1
                        netmask = netmask << 1 & 0xffffffff
                    netmask = count
                except:
                    pass
                if vips and line[1] not in vips:
                    continue
                str_IP.append(line[1])
                ifaces[iface]['v4'].append({
                    'inet': line[1],
                    'netmask': netmask,
                    'broadcast': line[5] if len(line) > 5 else None,
                })

        p1 = Popen(["ifconfig", iface, "inet6"], stdin=PIPE, stdout=PIPE)
        p2 = Popen(["grep", "inet6 "], stdin=p1.stdout, stdout=PIPE, encoding='utf8')
        output = p2.communicate()[0]
        if p2.returncode == 0:
            for line in output.split('\n'):
                if not line:
                    continue
                line = line.strip('\t').strip().split(' ')
                ifaces[iface]['v6'].append({
                    'addr': line[1].split('%')[0],
                    'prefixlen': line[3],
                })

    p1 = Popen(["cat", "/etc/resolv.conf"], stdin=PIPE, stdout=PIPE)
    p2 = Popen(["grep", "nameserver"], stdin=p1.stdout, stdout=PIPE, encoding='utf8')
    p1.wait()
    p2.wait()
    nss = []
    if p2.returncode == 0:
        output = p2.communicate()[0]
        for ns in output.split('\n')[:-1]:
            addr = ns.split(' ')[-1]
            nss.append(addr)

    p1 = Popen(["netstat", "-rn"], stdin=PIPE, stdout=PIPE)
    p2 = Popen(["grep", "^default"], stdin=p1.stdout, stdout=PIPE)
    p3 = Popen(["awk", "{print $2}"], stdin=p2.stdout, stdout=PIPE, encoding='utf8')
    p1.wait()
    p2.wait()
    p3.wait()
    default = None
    if p3.returncode == 0:
        output = p3.communicate()[0]
        default = output.split('\n')
    return str_IP


def get_thumb_print(ip, port):
    thumb_print = ''
    try:
        subprocess.Popen(
            [
                "openssl s_client -showcerts -connect " +
                ip +
                ":" +
                port +
                " < /dev/null | openssl x509 -outform PEM > servercert.pem"],
            stdout=subprocess.PIPE,
            shell=True,
            encoding='utf8')
        time.sleep(2)
        proc = subprocess.Popen(
            ["openssl x509 -noout -in servercert.pem -fingerprint -sha1"],
            stdout=subprocess.PIPE,
            shell=True,
            encoding='utf8')
        (out, err) = proc.communicate()
        thumb_print = out.split('=')[1].lstrip().rstrip()
        os.remove('servercert.pem')
        return thumb_print
    except Exception:
        return None


def get_plugin_file_name():
    try:
        paths = [os.path.join(
            settings.STATIC_ROOT, fname) for fname in os.listdir(
                settings.STATIC_ROOT
                )]
        file = sorted(
                [p for p in paths if '.zip'in p and 'plugin' in p],
                  key = os.path.getctime)[-1].split('/')[-1]
        if '.zip' in file and 'plugin' in file:
            return file
    except:
        return None


def get_plugin_version():
    try:
        err_message = 'Not available'
        paths = [os.path.join(
            settings.STATIC_ROOT, fname) for fname in os.listdir(
                settings.STATIC_ROOT
                )]
        file = sorted(
                [p for p in paths if '.zip'in p and 'plugin' in p],
                  key = os.path.getctime)[-1].split('/')[-1]
        if file.count('_') < 2 or file.count('.') < 3:
            return err_message
        version = file.split('_')[1]
        return version
    except Exception:
        return err_message


def zip_this_file(src_path, dest_path, Ftype):
    shutil.make_archive(dest_path, Ftype, src_path)


def zipdir(src_path, dest_path):
    assert os.path.isdir(src_path)
    with closing(ZipFile(dest_path, "w")) as z:

        for root, dirs, files in os.walk(src_path):
            for fn in files:
                absfn = os.path.join(root, fn)
                zfn = absfn[len(src_path) + len(os.sep):]
                z.write(absfn, zfn)


def extract_zip(src_path, dest_path):
    if not os.path.exists(dest_path):
        os.makedirs(dest_path)
    os.system("unzip " + src_path + " -d " + dest_path)


def remove_directory(dest_path):
    if os.path.exists(dest_path):
        shutil.rmtree(dest_path)


def update_plugin_zipfile(
        ip,
        username,
        password,
        port,
        install_mode,
        plugin_vesion_old, plugin_vesion_new):
    try:
        fname = get_plugin_file_name()
        if fname is None:
            return False

        pat = settings.STATIC_ROOT
        extract_zip(pat + '/' + fname, pat + '/plugin')
        extract_zip(
            pat + '/plugin/plugins/ixsystems-vcp-service.jar',
            pat + '/plugin/plugins/ixsystems-vcp-service')
        status_flag = create_propertyFile(
            pat +
            '/plugin/plugins/ixsystems-vcp-service/META-INF/config/install.properties',
            install_mode,
            plugin_vesion_old,
            plugin_vesion_new,
            ip,
            username,
            password,
            port,
            'Calsoft@')
        zipdir(pat + '/plugin/plugins/ixsystems-vcp-service',
               pat + '/plugin/plugins/ixsystems-vcp-service.jar')
        remove_directory(pat + '/plugin/plugins/ixsystems-vcp-service')
        zip_this_file(
            pat +
            '/plugin',
            pat +
            '/' +
            fname[
                0:len(fname) -
                4],
            'zip')
        remove_directory(pat + '/plugin')
        return status_flag
    except Exception as ex:
        return str(ex).replace("'", "").replace("<", "").replace(">", "")


def encrypt_string(password, key):
    cipher = DES.new(key, DES.MODE_CFB, key)
    resolved = cipher.encrypt(password.encode('ISO-8859-1'))
    return resolved.decode('ISO-8859-1')


def decrypt_string(str_ciph, key):
    # XXX: VCP Java plugin does not use this method.
    str_ciph = str_ciph.encode('ISO-8859-1')
    cipher = DES.new(key, DES.MODE_CFB, key)
    resolved = cipher.decrypt(str_ciph)
    return resolved.decode('ISO-8859-1')


def create_propertyFile(
        fpath,
        install_mode,
        plugin_vesion_old,
        plugin_vesion_new,
        host_ip,
        username,
        password,
        port,
        enc_key):
    try:
        Config = configparser.ConfigParser()
        cfgfile = open(fpath, 'w')
        Config.add_section('installation_parameter')
        Config.set('installation_parameter', 'ip', host_ip)
        Config.set('installation_parameter', 'username', username)
        Config.set('installation_parameter', 'port', port)
        Config.set('installation_parameter', 'password', encrypt_string(
            password, enc_key))
        Config.set('installation_parameter', 'install_mode', str(install_mode))
        Config.set(
            'installation_parameter',
            'plugin_version_old',
            str(plugin_vesion_old))
        Config.set(
            'installation_parameter',
            'plugin_version_new',
            str(plugin_vesion_new))
        Config.write(cfgfile)
        cfgfile.close()
        return True

    except Exception as ex:
        return str(ex).replace("'", "").replace("<", "").replace(">", "")
