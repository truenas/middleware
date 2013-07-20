import os
import platform
import pwd

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from fireflyUI.freenas import models, utils


class FireflyForm(forms.ModelForm):

    class Meta:
        model = models.Firefly
        widgets = {
            'admin_pw': forms.widgets.PasswordInput(),
            'port': forms.widgets.TextInput(),
        }
        exclude = (
            'enable',
            )

    def __init__(self, *args, **kwargs):
        self.jail_path = kwargs.pop('jail_path')
        super(FireflyForm, self).__init__(*args, **kwargs)

        if self.instance.admin_pw:
            self.fields['admin_pw'].required = False

        self.fields['mp3_dir'].widget = forms.widgets.TextInput(attrs={
            'data-dojo-type': 'freeadmin.form.PathSelector',
            'root': self.jail_path,
            'dirsonly': 'true',
            })

        self.fields['logfile'].widget = forms.widgets.TextInput(attrs={
            'data-dojo-type': 'freeadmin.form.PathSelector',
            'root': self.jail_path,
            'dirsonly': 'false',
            })

    def clean_admin_pw(self):
        admin_pw = self.cleaned_data.get("admin_pw")
        if not admin_pw:
            return self.instance.admin_pw
        return admin_pw

    def save(self, *args, **kwargs):
        obj = super(FireflyForm, self).save(*args, **kwargs)

        advanced_settings = {}
        for field in obj._meta.local_fields:
            if field.attname not in utils.firefly_advanced_vars:
                continue
            info = utils.firefly_advanced_vars.get(field.attname)
            value = getattr(obj, field.attname)
            if info["type"] == "checkbox":
                if value:
                    if info.get("on"):
                        advanced_settings[field.attname] = info["on"]
                else:
                    if info.get("off"):
                        advanced_settings[field.attname] = info["off"]

            elif info["type"] == "textbox" and value:
                advanced_settings[field.attname] = "%s %s" % (info["opt"], value)

        rcconf = os.path.join(utils.firefly_etc_path, "rc.conf")
        with open(rcconf, "w") as f:
            if obj.enable:
                f.write('firefly_enable="YES"\n')

            firefly_flags = ""
            for value in advanced_settings.values():
                firefly_flags += value + " "
            f.write('firefly_flags="%s"\n' % (firefly_flags, ))

        #if obj.download_dir:
        #    #os.system("/usr/sbin/chown -R firefly:firefly '%s'" % main_settings["firefly_download_dir"])
        #    os.chmod(obj.download_dir, 0o755)

        os.system(os.path.join(utils.firefly_pbi_path, "tweak-rcconf"))

        try:
            os.makedirs("/var/cache/mt-daapd")
            os.chown("/var/cache/mt-daapd", *pwd.getpwnam('daapd')[2:4])
        except Exception:
            pass

        with open(utils.firefly_config, "w") as f:
            f.write("[general]\n")
            f.write("web_root = /usr/pbi/firefly-%s/share/mt-daapd/admin-root\n" % (
                platform.machine(),
                ))
            f.write("port = %d\n" % (obj.port, ))
            f.write("admin_pw = %s\n" % (obj.admin_pw, ))
            f.write("db_type = %s\n" % ("sqlite3", ))
            f.write("db_parms = %s\n" % ("/var/db/mt-daapd", ))
            f.write("mp3_dir = %s\n" % (obj.mp3_dir, ))
            f.write("servername = %s\n" % (obj.servername, ))
            f.write("runas = %s\n" % ("daapd", ))
            f.write("extensions = %s\n" % (obj.extensions, ))
            f.write("logfile = %s\n" % (obj.logfile, ))
            f.write("rescan_interval = %d\n" % (obj.rescan_interval, ))
            f.write("always_scan = %d\n" % (obj.always_scan, ))
            f.write("scan_type = %d\n" % (obj.scan_type, ))
            f.write("\n[scanning]\n")
            f.write("process_playlists = %d\n" % (obj.process_playlists, ))
            f.write("process_itunes = %d\n" % (obj.process_itunes, ))
            f.write("process_m3u = %d\n" % (obj.process_m3u, ))
            if obj.auxiliary:
                f.write("%s\n" % (obj.auxiliary, ))
