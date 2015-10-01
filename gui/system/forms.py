# +
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

from collections import defaultdict, OrderedDict
from datetime import datetime
import cPickle as pickle
import json
import logging
import math
import os
import re
import stat
import string
import subprocess

from django.conf import settings
from django.contrib.formtools.wizard.views import SessionWizardView
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Q
from django.forms import FileField
from django.forms.formsets import BaseFormSet, formset_factory
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.utils.html import escapejs
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext as __

from dojango import forms
from freenasUI import choices
from freenasUI.account.forms import bsdUsersForm
from freenasUI.account.models import bsdGroups, bsdUsers
from freenasUI.common import humanize_size, humanize_number_si
from freenasUI.common.forms import ModelForm, Form
from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FreeNAS_LDAP
)

from freenasUI.directoryservice.forms import (
    ActiveDirectoryForm,
    LDAPForm,
    NISForm,
    NT4Form,
)
from freenasUI.directoryservice.models import (
    ActiveDirectory,
    LDAP,
    NIS,
    NT4,
)
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.connector import connection as dispatcher
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.services.models import (
    services,
    iSCSITarget,
    iSCSITargetAuthorizedInitiator,
    iSCSITargetExtent,
    iSCSITargetPortal,
    iSCSITargetPortalIP,
    iSCSITargetToExtent,
)
from freenasUI.sharing.models import (
    AFP_Share,
    CIFS_Share,
    NFS_Share
)
from freenasUI.storage.forms import VolumeAutoImportForm
from freenasUI.storage.models import Disk, Volume, Scrub
from freenasUI.system import models
from freenasUI.tasks.models import SMARTTest

log = logging.getLogger('system.forms')


def clean_path_execbit(path):
    """
    Make sure the hierarchy has the bit S_IXOTH set
    """
    current = path
    while True:
        try:
            mode = os.stat(current).st_mode
            if mode & stat.S_IXOTH == 0:
                raise forms.ValidationError(
                    _("The path '%s' requires execute permission bit") % (
                        current,
                    )
                )
        except OSError:
            break

        current = os.path.realpath(os.path.join(current, os.path.pardir))
        if current == '/':
            break


def clean_path_locked(mp):
    qs = Volume.objects.filter(vol_name=mp.replace('/mnt/', ''))
    if qs.exists():
        obj = qs[0]


class BootEnvAddForm(Form):

    name = forms.CharField(
        label=_('Name'),
        max_length=50,
    )

    def __init__(self, *args, **kwargs):
        self._source = kwargs.pop('source', None)
        super(BootEnvAddForm, self).__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not re.search(r'^[a-z0-9_-]+$', name, re.I):
            raise forms.ValidationError(
                _('Only alphanumeric, underscores and dashes are allowed.')
            )
        return name

    def save(self, *args, **kwargs):
        result = dispatcher.call_task_sync('boot.environments.create', self.cleaned_data.get('name'), self._source)
        if result['state'] != 'FINISHED':
            raise MiddlewareError(_(result['error']['message']))


class BootEnvRenameForm(Form):

    name = forms.CharField(
        label=_('Name'),
        max_length=50,
    )

    def __init__(self, *args, **kwargs):
        self._name = kwargs.pop('name')
        super(BootEnvRenameForm, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        result = dispatcher.call_task_sync('boot.environments.rename', self._name, self.cleaned_data.get('name'))
        if result['state'] != 'FINISHED':
            raise MiddlewareError(_(result['error']['message']))


class BootEnvPoolAttachForm(Form):

    attach_disk = forms.ChoiceField(
        choices=(),
        widget=forms.Select(),
        label=_('Member disk'))

    def __init__(self, *args, **kwargs):
        self.guid = kwargs.pop('guid')
        super(BootEnvPoolAttachForm, self).__init__(*args, **kwargs)
        self.fields['attach_disk'].choices = self._populate_disk_choices()
        self.fields['attach_disk'].choices.sort(
            key=lambda a: float(
                re.sub(r'^.*?([0-9]+)[^0-9]*([0-9]*).*$', r'\1.\2', a[0])
            )
        )

    def _populate_disk_choices(self):

        diskchoices = dict()
        used_disks = []
        for v in Volume.objects.all():
            used_disks.extend(v.get_disks())

        # Grab partition list
        # NOTE: This approach may fail if device nodes are not accessible.
        disks = notifier().get_disks()

        for disk in disks:
            if disk in used_disks:
                continue
            devname, capacity = disks[disk]['devname'], disks[disk]['capacity']
            capacity = humanize_number_si(int(capacity))
            diskchoices[devname] = "%s (%s)" % (devname, capacity)

        choices = diskchoices.items()
        choices.sort(key=lambda a: float(
            re.sub(r'^.*?([0-9]+)[^0-9]*([0-9]*).*$', r'\1.\2', a[0])
        ))
        return choices

    def done(self):
        devname = os.path.join('/dev', self.cleaned_data['attach_disk'])
        result = dispatcher.call_task_sync('boot.attach_disk', self.guid, devname)
        if result['state'] != 'FINISHED':
            raise MiddlewareError(_(result['error']['message']))

        return True


class BootEnvPoolReplaceForm(Form):

    replace_disk = forms.ChoiceField(
        choices=(),
        widget=forms.Select(),
        label=_('Member disk'))

    def __init__(self, *args, **kwargs):
        self.label = kwargs.pop('label')
        super(BootEnvPoolReplaceForm, self).__init__(*args, **kwargs)
        self.fields['replace_disk'].choices = self._populate_disk_choices()
        self.fields['replace_disk'].choices.sort(
            key=lambda a: float(
                re.sub(r'^.*?([0-9]+)[^0-9]*([0-9]*).*$', r'\1.\2', a[0])
            )
        )

    def _populate_disk_choices(self):

        diskchoices = dict()
        used_disks = []
        for v in Volume.objects.all():
            used_disks.extend(v.get_disks())

        # Grab partition list
        # NOTE: This approach may fail if device nodes are not accessible.
        disks = notifier().get_disks()

        for disk in disks:
            if disk in used_disks:
                continue
            devname, capacity = disks[disk]['devname'], disks[disk]['capacity']
            capacity = humanize_number_si(int(capacity))
            diskchoices[devname] = "%s (%s)" % (devname, capacity)

        choices = diskchoices.items()
        choices.sort(key=lambda a: float(
            re.sub(r'^.*?([0-9]+)[^0-9]*([0-9]*).*$', r'\1.\2', a[0])
        ))
        return choices

    def done(self):
        devname = self.cleaned_data['replace_disk']

        rv = notifier().bootenv_replace_disk(self.label, devname)
        if rv == 0:
            notifier().sync_disks()
            return True
        else:
            return False


class CommonWizard(SessionWizardView):

    template_done = 'system/done.html'

    def done(self, form_list, **kwargs):
        response = render_to_response(self.template_done, {
            #'form_list': form_list,
            'retval': getattr(self, 'retval', None),
        })
        if not self.request.is_ajax():
            response.content = (
                "<html><body><textarea>"
                + response.content +
                "</textarea></boby></html>"
            )
        return response

    def process_step(self, form):
        proc = super(CommonWizard, self).process_step(form)
        """
        We execute the form done method if there is one, for each step
        """
        if hasattr(form, 'done'):
            retval = form.done(
                request=self.request,
                form_list=self.form_list,
                wizard=self)
            if self.get_step_index() == self.steps.count - 1:
                self.retval = retval
        return proc

    def render_to_response(self, context, **kwargs):
        response = super(CommonWizard, self).render_to_response(
            context,
            **kwargs)
        # This is required for the workaround dojo.io.frame for file upload
        if not self.request.is_ajax():
            return HttpResponse(
                "<html><body><textarea>"
                + response.rendered_content +
                "</textarea></boby></html>"
            )
        return response


class FileWizard(CommonWizard):

    file_storage = FileSystemStorage(location='/var/tmp/firmware')


class ManualUpdateWizard(FileWizard):

    def get_template_names(self):
        return [
            'system/manualupdate_wizard_%s.html' % self.get_step_index(),
        ]

    def done(self, form_list, **kwargs):
        cleaned_data = self.get_all_cleaned_data()
        assert ('sha256' in cleaned_data)
        updatefile = cleaned_data.get('updatefile')

        _n = notifier()
        path = self.file_storage.path(updatefile.file.name)

        try:
            if not _n.is_freenas() and _n.failover_licensed():
                s = _n.failover_rpc(timeout=10)
                s.notifier('create_upload_location', None, None)
                _n.sync_file_send(s, path, '/var/tmp/firmware/update.tar.xz')
                s.update_manual(
                    '/var/tmp/firmware/update.tar.xz',
                    cleaned_data['sha256'].encode('ascii', 'ignore'),
                )
                try:
                    s.reboot()
                except:
                    pass
                response = render_to_response('failover/update_standby.html')
            else:
                task = dispatcher.call_task_sync(
                    'update.manual',
                    path,
                    cleaned_data['sha256'].encode('ascii', 'ignore'),
                )
                if task['error']:
                    raise MiddlewareError(task['error']['message'])
                _n.destroy_upload_location()
                self.request.session['allow_reboot'] = True
                response = render_to_response('system/done.html', {
                    'retval': getattr(self, 'retval', None),
                })
        except:
            try:
                self.file_storage.delete(updatefile.name)
            except:
                log.warn('Failed to delete uploaded file', exc_info=True)
            raise

        if not self.request.is_ajax():
            response.content = (
                "<html><body><textarea>"
                + response.content +
                "</textarea></boby></html>"
            )
        return response


class SettingsForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.Settings
        widgets = {
            'stg_timezone': forms.widgets.FilteringSelect(),
            'stg_language': forms.widgets.FilteringSelect(),
            'stg_kbdmap': forms.widgets.FilteringSelect(),
            'stg_guiport': forms.widgets.TextInput(),
            'stg_guihttpsport': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(SettingsForm, self).__init__(*args, **kwargs)
        self.instance._original_stg_guiprotocol = self.instance.stg_guiprotocol
        self.instance._original_stg_guiaddress = self.instance.stg_guiaddress
        self.instance._original_stg_guiport = self.instance.stg_guiport
        self.instance._original_stg_guihttpsport = self.instance.stg_guihttpsport
        self.instance._original_stg_guihttpsredirect = self.instance.stg_guihttpsredirect
        self.instance._original_stg_syslogserver = (
            self.instance.stg_syslogserver
        )
        self.instance._original_stg_guicertificate = self.instance.stg_guicertificate
        self.fields['stg_language'].choices = settings.LANGUAGES
        self.fields['stg_language'].label = _("Language (Require UI reload)")
        self.fields['stg_guiaddress'] = forms.ChoiceField(
            label=self.fields['stg_guiaddress'].label
        )
        self.fields['stg_guiaddress'].choices = [
            ['0.0.0.0', '0.0.0.0']
        ] + list(choices.IPChoices(ipv6=False))

        self.fields['stg_guiv6address'] = forms.ChoiceField(
            label=self.fields['stg_guiv6address'].label
        )
        self.fields['stg_guiv6address'].choices = [
            ['::', '::']
        ] + list(choices.IPChoices(ipv4=False))

    def clean(self):
        cdata = self.cleaned_data
        proto = cdata.get("stg_guiprotocol")
        if proto == "http":
            return cdata

        certificate = cdata["stg_guicertificate"]
        if not certificate:
            raise forms.ValidationError(
                "HTTPS specified without certificate")

        return cdata

    def save(self):
        super(SettingsForm, self).save()
        if self.instance._original_stg_syslogserver != self.instance.stg_syslogserver:
            notifier().restart("syslogd")
        notifier().reload("timeservices")

    def done(self, request, events):
        if (
            self.instance._original_stg_guiprotocol != self.instance.stg_guiprotocol or
            self.instance._original_stg_guiaddress != self.instance.stg_guiaddress or
            self.instance._original_stg_guiport != self.instance.stg_guiport or
            self.instance._original_stg_guihttpsport != self.instance.stg_guihttpsport or
            self.instance._original_stg_guihttpsredirect != self.instance.stg_guihttpsredirect or
            self.instance._original_stg_guicertificate != self.instance.stg_guicertificate
        ):
            if self.instance.stg_guiaddress == "0.0.0.0":
                address = request.META['HTTP_HOST'].split(':')[0]
            else:
                address = self.instance.stg_guiaddress
            if self.instance.stg_guiprotocol == 'httphttps':
                protocol = 'http'
            else:
                protocol = self.instance.stg_guiprotocol
            newurl = "%s://%s" % (
                protocol,
                address
            )
            if self.instance.stg_guiport and protocol == 'http':
                newurl += ":" + str(self.instance.stg_guiport)
            elif self.instance.stg_guihttpsport and protocol == 'https':
                newurl += ":" + str(self.instance.stg_guihttpsport)
            notifier().start_ssl("nginx")
            if self.instance._original_stg_guiprotocol != self.instance.stg_guiprotocol:
                events.append("evilrestartHttpd('%s')" % newurl)
            else:
                events.append("restartHttpd('%s')" % newurl)


class NTPForm(ModelForm):

    force = forms.BooleanField(
        label=_("Force"),
        required=False,
        help_text=_(
            "Continue operation if the server could not be reached/validated."
        ),
    )

    class Meta:
        fields = '__all__'
        model = models.NTPServer

    def save(self):
        obj = super(NTPForm, self).save(commit=False)
        obj.save(extra_args=[self.cleaned_data.get('force')])


class AdvancedForm(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.Advanced
        widgets = {
            'adv_system_dataset_pool': forms.Select(
                choices=choices.PoolChoices()
            ),
        }

    def __init__(self, *args, **kwargs):
        from freenasUI.middleware.connector import connection as dispatcher
        super(AdvancedForm, self).__init__(*args, **kwargs)
        self.instance._original_adv_consolemenu = self.instance.adv_consolemenu
        self.instance._original_adv_powerdaemon = self.instance.adv_powerdaemon
        self.instance._original_adv_serialconsole = (
            self.instance.adv_serialconsole
        )
        self.instance._original_adv_serialspeed = self.instance.adv_serialspeed
        self.instance._original_adv_serialport = self.instance.adv_serialport
        self.instance._original_adv_consolemsg = self.instance.adv_consolemsg
        self.instance._original_adv_advancedmode = (
            self.instance.adv_advancedmode
        )
        self.instance._original_adv_autotune = self.instance.adv_autotune
        self.instance._original_adv_debugkernel = self.instance.adv_debugkernel
        self.instance._original_adv_periodic_notifyuser = self.instance.adv_periodic_notifyuser

        ports = dispatcher.call_sync('system.advanced.serial_ports')
        if not ports:
            ports = ['0x2f8']

        self.fields['adv_serialport'].widget = forms.widgets.Select(
            choices=[(p, p) for p in ports])

    def done(self, request, events):
        if self.instance._original_adv_consolemsg != self.instance.adv_consolemsg:
            if self.instance.adv_consolemsg:
                events.append("_msg_start()")
            else:
                events.append("_msg_stop()")
        if self.instance._original_adv_advancedmode != self.instance.adv_advancedmode:
            #Invalidate cache
            request.session.pop("adv_mode", None)
        if (
            self.instance._original_adv_autotune != self.instance.adv_autotune
            and self.instance.adv_autotune is True
        ):
            events.append("refreshTree()")


class EmailForm(ModelForm):
    em_pass1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput,
        required=False)
    em_pass2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput,
        help_text=_("Enter the same password as above, for verification."),
        required=False)

    class Meta:
        model = models.Email
        exclude = ('em_pass',)

    def __init__(self, *args, **kwargs):
        super(EmailForm, self).__init__(*args, **kwargs)
        try:
            self.fields['em_pass1'].initial = self.instance.em_pass
            self.fields['em_pass2'].initial = self.instance.em_pass
        except:
            pass
        self.fields['em_smtp'].widget.attrs['onChange'] = (
            'toggleGeneric("id_em_smtp", ["id_em_pass1", "id_em_pass2", '
            '"id_em_user"], true);'
        )
        ro = True

        if len(self.data) > 0:
            if self.data.get("em_smtp", None) == "on":
                ro = False
        else:
            if self.instance.em_smtp is True:
                ro = False
        if ro:
            self.fields['em_user'].widget.attrs['disabled'] = 'disabled'
            self.fields['em_pass1'].widget.attrs['disabled'] = 'disabled'
            self.fields['em_pass2'].widget.attrs['disabled'] = 'disabled'

    def clean_em_user(self):
        if (
            self.cleaned_data['em_smtp'] is True and
            self.cleaned_data['em_user'] == ""
        ):
            raise forms.ValidationError(_("This field is required"))
        return self.cleaned_data['em_user']

    def clean_em_pass1(self):
        if (
            self.cleaned_data['em_smtp'] is True and
            self.cleaned_data['em_pass1'] == ""
        ):
            if self.instance.em_pass:
                return self.instance.em_pass
            raise forms.ValidationError(_("This field is required"))
        return self.cleaned_data['em_pass1']

    def clean_em_pass2(self):
        if (
            self.cleaned_data['em_smtp'] is True and
            self.cleaned_data.get('em_pass2', "") == ""
        ):
            if self.instance.em_pass:
                return self.instance.em_pass
            raise forms.ValidationError(_("This field is required"))
        pass1 = self.cleaned_data.get("em_pass1", "")
        pass2 = self.cleaned_data.get("em_pass2", "")
        if pass1 != pass2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return pass2

    def save(self, commit=True):
        email = super(EmailForm, self).save(commit=False)
        if commit:
            email.em_pass = self.cleaned_data['em_pass2']
            email.save()
        return email


class ManualUpdateTemporaryLocationForm(Form):
    mountpoint = forms.ChoiceField(
        label=_("Place to temporarily place update file"),
        help_text=_(
            "The system will use this place to temporarily store the "
            "update file before it's being applied."),
        choices=(),
        widget=forms.Select(attrs={'class': 'required'}),
    )

    def clean_mountpoint(self):
        mp = self.cleaned_data.get("mountpoint")
        if mp.startswith('/'):
            clean_path_execbit(mp)
        clean_path_locked(mp)
        return mp

    def __init__(self, *args, **kwargs):
        super(ManualUpdateTemporaryLocationForm, self).__init__(*args, **kwargs)
        self.fields['mountpoint'].choices = [
            ('/mnt/%s' % x.vol_name, '/mnt/%s' % x.vol_name)
            for x in Volume.objects.all()
        ]
        self.fields['mountpoint'].choices.append(
            (':temp:', _('Memory device'))
        )

    def done(self, *args, **kwargs):
        mp = str(self.cleaned_data["mountpoint"])
        if mp == ":temp:":
            notifier().create_upload_location()
        else:
            notifier().change_upload_location(mp)


class ManualUpdateUploadForm(Form):
    updatefile = FileField(label=_("Update file to be installed"), required=True)
    sha256 = forms.CharField(
        label=_("SHA256 sum for the image"),
        required=True
    )


class ConfigUploadForm(Form):
    config = FileField(label=_("New config to be installed"))


class TunableForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.Tunable

    def clean_tun_comment(self):
        return self.cleaned_data.get('tun_comment').strip()

    def save(self):
        super(TunableForm, self).save()
        try:
            if self.instance.tun_type == 'RC':
                os.unlink('/var/tmp/freenas_config.md5')
                notifier()._system("sh /etc/rc.conf.local")
        except:
            pass


class RegistrationForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.Registration

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)

    def save(self):
        super(RegistrationForm, self).save()
        registration_info = {
            'reg_firstname': None,
            'reg_lastname': None,
            'reg_company': None,
            'reg_address': None,
            'reg_city': None,
            'reg_state': None,
            'reg_zip': None,
            'reg_email': None,
            'reg_homephone': None,
            'reg_cellphone': None,
            'reg_workphone': None
        }

        for key in registration_info:
            if self.cleaned_data[key]:
                registration_info[key] = str(self.cleaned_data[key])

        f = open("/usr/local/etc/registration", "w")
        f.write(json.dumps(registration_info))
        f.close()


class UpdateForm(ModelForm):

    curtrain = forms.CharField(
        label=_('Current Train'),
        widget=forms.TextInput(attrs={'readonly': True, 'disabled': True}),
        required=False,
    )

    class Meta:
        fields = '__all__'
        model = models.Update

    def __init__(self, *args, **kwargs):
        super(UpdateForm, self).__init__(*args, **kwargs)
        self.fields['curtrain'].initial = dispatcher.call_sync('update.get_current_train')


class CertificateAuthorityForm(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.CertificateAuthority

    def save(self):
        super(CertificateAuthorityForm, self).save()
        notifier().start("ix-ssl")


class CertificateAuthorityEditForm(ModelForm):
    cert_name = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_name').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_name').help_text
    )
    cert_certificate = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_certificate').verbose_name,
        widget=forms.Textarea(),
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_certificate').help_text
    )
    cert_serial = forms.IntegerField(
        label=models.CertificateAuthority._meta.get_field('cert_serial').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_serial').help_text,
    )

    def save(self):
        obj = super(CertificateAuthorityEditForm, self).save(commit=False)
        obj.save(method='crypto.certificates.ca_update', data=self.cleaned_data)
        notifier().start("ix-ssl")

    class Meta:
        fields = [
            'cert_name',
            'cert_certificate',
            'cert_privatekey',
            'cert_serial'
        ]
        model = models.CertificateAuthority


class CertificateAuthorityImportForm(ModelForm):
    cert_name = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_name').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_name').help_text
    )
    cert_certificate = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_certificate').verbose_name,
        widget=forms.Textarea(),
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_certificate').help_text,
    )
    cert_passphrase = forms.CharField(
        label=_("Passphrase"),
        required=False,
        help_text=_("Passphrase for encrypted private keys"),
        widget=forms.PasswordInput(render_value=True),
    )
    cert_passphrase2 = forms.CharField(
        label=_("Confirm Passphrase"),
        required=False,
        widget=forms.PasswordInput(render_value=True),
    )
    cert_serial = forms.IntegerField(
        label=models.CertificateAuthority._meta.get_field('cert_serial').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_serial').help_text,
    )

    def clean_cert_passphrase2(self):
        cdata = self.cleaned_data
        passphrase = cdata.get('cert_passphrase')
        passphrase2 = cdata.get('cert_passphrase2')

        if passphrase and passphrase != passphrase2:
            raise forms.ValidationError(_(
                'Passphrase confirmation does not match.'
            ))
        return passphrase

    def save(self):
        obj = super(CertificateAuthorityImportForm, self).save(commit=False)
        self.cleaned_data['passphrase'] = self.cleaned_data.pop('cert_passphrase', None)
        self.cleaned_data.pop('cert_passphrase2', None)
        privatekey = self.cleaned_data.get('cert_privatekey')
        if not privatekey:
            self.cleaned_data.pop('cert_privatekey')
        obj.save(method='crypto.certificates.ca_import', data=self.cleaned_data)
        notifier().start("ix-ssl")
        return obj

    class Meta:
        fields = [
            'cert_name',
            'cert_certificate',
            'cert_privatekey',
            'cert_passphrase',
            'cert_passphrase2',
            'cert_serial'
        ]
        model = models.CertificateAuthority


class CertificateAuthorityCreateInternalForm(ModelForm):
    cert_name = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_name').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_name').help_text
    )
    cert_key_length = forms.ChoiceField(
        label=models.CertificateAuthority._meta.get_field('cert_key_length').verbose_name,
        required=True,
        choices=choices.CERT_KEY_LENGTH_CHOICES,
        initial=2048
    )
    cert_digest_algorithm = forms.ChoiceField(
        label=models.CertificateAuthority._meta.get_field('cert_digest_algorithm').verbose_name,
        required=True,
        choices=choices.CERT_DIGEST_ALGORITHM_CHOICES,
        initial='SHA256'
    )
    cert_lifetime = forms.IntegerField(
        label=models.CertificateAuthority._meta.get_field('cert_lifetime').verbose_name,
        required=True,
        initial=3650
    )
    cert_country = forms.ChoiceField(
        label=models.CertificateAuthority._meta.get_field('cert_country').verbose_name,
        required=True,
        choices=choices.COUNTRY_CHOICES(), 
        initial='US',
        help_text=models.CertificateAuthority._meta.get_field('cert_country').help_text
    )
    cert_state = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_state').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_state').help_text
    )
    cert_city = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_city').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_city').help_text
    )
    cert_organization = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_organization').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_organization').help_text
    )
    cert_email = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_email').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_email').help_text,
    )
    cert_common = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_common').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_common').help_text
    )

    def clean_cert_key_length(self):
        key = self.cleaned_data.get('cert_key_length')
        if key:
            return int(key)

    def save(self):
        obj = super(CertificateAuthorityCreateInternalForm, self).save(commit=False)
        obj.save(method='crypto.certificates.ca_internal_create', data=self.cleaned_data)
        notifier().start("ix-ssl")
        return obj

    class Meta:
        fields = [
            'cert_name',
            'cert_key_length',
            'cert_digest_algorithm',
            'cert_lifetime',
            'cert_country',
            'cert_state',
            'cert_city',
            'cert_organization',
            'cert_email',
            'cert_common'
        ]
        model = models.CertificateAuthority


class CertificateAuthorityCreateIntermediateForm(ModelForm):
    cert_name = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_name').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_name').help_text
    )
    cert_key_length = forms.ChoiceField(
        label=models.CertificateAuthority._meta.get_field('cert_key_length').verbose_name,
        required=True,
        choices=choices.CERT_KEY_LENGTH_CHOICES,
        initial=2048
    )
    cert_digest_algorithm = forms.ChoiceField(
        label=models.CertificateAuthority._meta.get_field('cert_digest_algorithm').verbose_name,
        required=True,
        choices=choices.CERT_DIGEST_ALGORITHM_CHOICES,
        initial='SHA256'
    )
    cert_lifetime = forms.IntegerField(
        label=models.CertificateAuthority._meta.get_field('cert_lifetime').verbose_name,
        required=True,
        initial=3650
    )
    cert_country = forms.ChoiceField(
        label=models.CertificateAuthority._meta.get_field('cert_country').verbose_name,
        required=True,
        choices=choices.COUNTRY_CHOICES(),
        initial='US',
        help_text=models.CertificateAuthority._meta.get_field('cert_country').help_text
    )
    cert_state = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_state').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_state').help_text,
    )
    cert_city = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_city').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_city').help_text
    )
    cert_organization = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_organization').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_organization').help_text
    )
    cert_email = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_email').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_email').help_text
    )
    cert_common = forms.CharField(
        label=models.CertificateAuthority._meta.get_field('cert_common').verbose_name,
        required=True,
        help_text=models.CertificateAuthority._meta.get_field('cert_common').help_text
    )

    def __init__(self, *args, **kwargs):
        super(CertificateAuthorityCreateIntermediateForm, self).__init__(*args, **kwargs)

        self.fields['cert_signedby'].required = True
        self.fields['cert_signedby'].queryset = \
            models.CertificateAuthority.objects.exclude(
                Q(cert_certificate__isnull=True) |
                Q(cert_privatekey__isnull=True) |
                Q(cert_certificate__exact='') |
                Q(cert_privatekey__exact='')
            )
        self.fields['cert_signedby'].widget.attrs["onChange"] = (
            "javascript:CA_autopopulate();"
        )

    def clean_cert_key_length(self):
        key = self.cleaned_data.get('cert_key_length')
        if key:
            return int(key)

    def save(self):
        obj = super(CertificateAuthorityCreateIntermediateForm, self).save(commit=False)
        obj.save(method='crypto.certificates.ca_intermediate_create', data=self.cleaned_data)
        notifier().start("ix-ssl")
        return obj

    class Meta:
        fields = [
            'cert_signedby',
            'cert_name',
            'cert_key_length',
            'cert_digest_algorithm',
            'cert_lifetime',
            'cert_country',
            'cert_state',
            'cert_city',
            'cert_organization',
            'cert_email',
            'cert_common'
        ]
        model = models.CertificateAuthority


class CertificateForm(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.Certificate

    def save(self):
        super(CertificateForm, self).save()
        notifier().start("ix-ssl")


class CertificateEditForm(ModelForm):
    cert_name = forms.CharField(
        label=models.Certificate._meta.get_field('cert_name').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_name').help_text
    )
    cert_certificate = forms.CharField(
        label=models.Certificate._meta.get_field('cert_certificate').verbose_name,
        widget=forms.Textarea(),
        required=True,
        help_text=models.Certificate._meta.get_field('cert_certificate').help_text
    )

    def __init__(self, *args, **kwargs):
        super(CertificateEditForm, self).__init__(*args, **kwargs)

        self.fields['cert_name'].widget.attrs['readonly'] = True
        self.fields['cert_certificate'].widget.attrs['readonly'] = True
        self.fields['cert_privatekey'].widget.attrs['readonly'] = True

    def save(self):
        super(CertificateEditForm, self).save(commit=False)
        notifier().start("ix-ssl") 

    class Meta:
        fields = [
            'cert_name',
            'cert_certificate',
            'cert_privatekey'
        ]
        model = models.Certificate


class CertificateCSREditForm(ModelForm):
    cert_name = forms.CharField(
        label=models.Certificate._meta.get_field('cert_name').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_name').help_text
    )
    cert_CSR = forms.CharField(
        label=models.Certificate._meta.get_field('cert_CSR').verbose_name,
        widget=forms.Textarea(),
        required=True,
        help_text=models.Certificate._meta.get_field('cert_CSR').help_text
    )
    cert_certificate = forms.CharField(
        label=models.Certificate._meta.get_field('cert_certificate').verbose_name,
        widget=forms.Textarea(),
        required=True,
        help_text=models.Certificate._meta.get_field('cert_certificate').help_text
    )

    def __init__(self, *args, **kwargs):
        super(CertificateCSREditForm, self).__init__(*args, **kwargs)

        self.fields['cert_name'].widget.attrs['readonly'] = True
        self.fields['cert_CSR'].widget.attrs['readonly'] = True

    def save(self):
        obj = super(CertificateCSREditForm, self).save(commit=False)
        obj.save(
            method='crypto.certificates.csr_update',
            data={'certificate': self.cleaned_data.get('cert_certificate')},
        )
        notifier().start("ix-ssl")
        return obj

    class Meta:
        fields = [
            'cert_name',
            'cert_CSR',
            'cert_certificate'
        ]
        model = models.Certificate


class CertificateImportForm(ModelForm):
    cert_name = forms.CharField(
        label=models.Certificate._meta.get_field('cert_name').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_name').help_text
    )
    cert_certificate = forms.CharField(
        label=models.Certificate._meta.get_field('cert_certificate').verbose_name,
        widget=forms.Textarea(),
        required=True,
        help_text=models.Certificate._meta.get_field('cert_certificate').help_text
    )
    cert_privatekey = forms.CharField(
        label=models.Certificate._meta.get_field('cert_privatekey').verbose_name,
        widget=forms.Textarea(),
        required=True,
        help_text=models.Certificate._meta.get_field('cert_privatekey').help_text
    )
    cert_passphrase = forms.CharField(
        label=_("Passphrase"),
        required=False,
        help_text=_("Passphrase for encrypted private keys"),
        widget=forms.PasswordInput(render_value=True),
    )
    cert_passphrase2 = forms.CharField(
        label=_("Confirm Passphrase"),
        required=False,
        widget=forms.PasswordInput(render_value=True),
    )

    def clean_cert_passphrase2(self):
        cdata = self.cleaned_data
        passphrase = cdata.get('cert_passphrase')
        passphrase2 = cdata.get('cert_passphrase2')

        if passphrase and passphrase != passphrase2:
            raise forms.ValidationError(_(
                'Passphrase confirmation does not match.'
            ))
        return passphrase

    def save(self):
        obj = super(CertificateImportForm, self).save(commit=False)
        self.cleaned_data['passphrase'] = self.cleaned_data.pop('cert_passphrase', None)
        self.cleaned_data.pop('cert_passphrase2', None)
        obj.save(
            method='crypto.certificates.cert_import',
            data=self.cleaned_data,
        )
        notifier().start("ix-ssl")
        return obj

    class Meta:
        fields = [
            'cert_name',
            'cert_certificate',
            'cert_privatekey',
            'cert_passphrase'
        ]
        model = models.Certificate


class CertificateCreateInternalForm(ModelForm):
    cert_name = forms.CharField(
        label=models.Certificate._meta.get_field('cert_name').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_name').help_text
    )
    cert_key_length = forms.ChoiceField(
        label=models.Certificate._meta.get_field('cert_key_length').verbose_name,
        required=True,
        choices=choices.CERT_KEY_LENGTH_CHOICES,
        initial=2048
    )
    cert_digest_algorithm = forms.ChoiceField(
        label=models.Certificate._meta.get_field('cert_digest_algorithm').verbose_name,
        required=True,
        choices=choices.CERT_DIGEST_ALGORITHM_CHOICES,
        initial='SHA256'
    )
    cert_lifetime = forms.IntegerField(
        label=models.Certificate._meta.get_field('cert_lifetime').verbose_name,
        required=True,
        initial=3650
    )
    cert_country = forms.ChoiceField(
        label=models.Certificate._meta.get_field('cert_country').verbose_name,
        required=True,
        choices=choices.COUNTRY_CHOICES(), 
        initial='US',
        help_text=models.Certificate._meta.get_field('cert_country').help_text
    )
    cert_state = forms.CharField(
        label=models.Certificate._meta.get_field('cert_state').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_state').help_text
    )
    cert_city = forms.CharField(
        label=models.Certificate._meta.get_field('cert_city').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_city').help_text
    )
    cert_organization = forms.CharField(
        label=models.Certificate._meta.get_field('cert_organization').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_organization').help_text
    )
    cert_email = forms.CharField(
        label=models.Certificate._meta.get_field('cert_email').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_email').help_text
    )
    cert_common = forms.CharField(
        label=models.Certificate._meta.get_field('cert_common').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_common').help_text
    )

    def __init__(self, *args, **kwargs):
        super(CertificateCreateInternalForm, self).__init__(*args, **kwargs)

        self.fields['cert_signedby'].required = True
        self.fields['cert_signedby'].queryset = \
            models.CertificateAuthority.objects.exclude(
                Q(cert_certificate__isnull=True) |
                Q(cert_privatekey__isnull=True) |
                Q(cert_certificate__exact='') |
                Q(cert_privatekey__exact='')
            )
        self.fields['cert_signedby'].widget.attrs["onChange"] = (
            "javascript:CA_autopopulate();"
        )

    def clean_cert_key_length(self):
        key = self.cleaned_data.get('cert_key_length')
        if key:
            return int(key)

    def save(self):
        obj = super(CertificateCreateInternalForm, self).save(commit=False)
        obj.save(
            method='crypto.certificates.cert_internal_create',
            data=self.cleaned_data,
        )
        notifier().start("ix-ssl")
        return obj

    class Meta:
        fields = [
            'cert_signedby',
            'cert_name',
            'cert_key_length',
            'cert_digest_algorithm',
            'cert_lifetime',
            'cert_country',
            'cert_state',
            'cert_city',
            'cert_organization',
            'cert_email',
            'cert_common'
        ]
        model = models.Certificate


class CertificateCreateCSRForm(ModelForm):
    cert_name = forms.CharField(
        label=models.Certificate._meta.get_field('cert_name').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_name').help_text
    )
    cert_key_length = forms.ChoiceField(
        label=models.Certificate._meta.get_field('cert_key_length').verbose_name,
        required=True,
        choices=choices.CERT_KEY_LENGTH_CHOICES,
        initial=2048
    )
    cert_digest_algorithm = forms.ChoiceField(
        label=models.Certificate._meta.get_field('cert_digest_algorithm').verbose_name,
        required=True,
        choices=choices.CERT_DIGEST_ALGORITHM_CHOICES,
        initial='SHA256'
    )
    cert_country = forms.ChoiceField(
        label=models.Certificate._meta.get_field('cert_country').verbose_name,
        required=True,
        choices=choices.COUNTRY_CHOICES(), 
        initial='US',
        help_text=models.Certificate._meta.get_field('cert_country').help_text
    )
    cert_state = forms.CharField(
        label=models.Certificate._meta.get_field('cert_state').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_state').help_text
    )
    cert_city = forms.CharField(
        label=models.Certificate._meta.get_field('cert_city').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_city').help_text,
    )
    cert_organization = forms.CharField(
        label=models.Certificate._meta.get_field('cert_organization').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_organization').help_text
    )
    cert_email = forms.CharField(
        label=models.Certificate._meta.get_field('cert_email').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_email').help_text
    )
    cert_common = forms.CharField(
        label=models.Certificate._meta.get_field('cert_common').verbose_name,
        required=True,
        help_text=models.Certificate._meta.get_field('cert_common').help_text
    )

    def clean_cert_key_length(self):
        key = self.cleaned_data.get('cert_key_length')
        if key:
            return int(key)

    def save(self):
        obj = super(CertificateCreateCSRForm, self).save(commit=False)
        obj.save(
            method='crypto.certificates.csr_create',
            data=self.cleaned_data,
        )
        notifier().start("ix-ssl")
        return obj

    class Meta:
        fields = [
            'cert_name',
            'cert_key_length',
            'cert_digest_algorithm',
            'cert_country',
            'cert_state',
            'cert_city',
            'cert_organization',
            'cert_email',
            'cert_common'
        ]
        model = models.Certificate


class BackupForm(Form):
    def __init__(self, *args, **kwargs):
        super(BackupForm, self).__init__(*args, **kwargs)

    backup_hostname = forms.CharField(
        label=_("Hostname or IP address"),
        required=True)

    backup_username = forms.CharField(
        label=_("User name"),
        required=True)

    backup_password = forms.CharField(
        label=_("Password"),
        required=False,
        widget=forms.widgets.PasswordInput(),
    )

    backup_password2 = forms.CharField(
        label=_("Confirm Password"),
        required=False,
        widget=forms.widgets.PasswordInput(),
    )

    backup_directory = forms.CharField(
        label=_("Remote directory"),
        required=True)

    backup_data = forms.BooleanField(
        label=_("Backup data"),
        required=False)

    backup_compression = forms.BooleanField(
        label=_("Compress backup"),
        required=False)

    backup_auth_keys = forms.BooleanField(
        label=_("Use key authentication"),
        required=False)

    def clean_backup_password2(self):
        pwd = self.cleaned_data.get('backup_password')
        pwd2 = self.cleaned_data.get('backup_password2')
        if pwd and pwd != pwd2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return pwd2
