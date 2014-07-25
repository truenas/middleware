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
import cPickle as pickle
import json
import logging
import math
import os
import re
import stat
import subprocess
import tempfile

from django.conf import settings
from django.contrib.formtools.wizard.views import SessionWizardView
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.forms import FileField
from django.forms.formsets import BaseFormSet, formset_factory
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext as __

from dojango import forms
from freenasUI import choices
from freenasUI.account.models import bsdGroups, bsdUsers
from freenasUI.common import humanize_size
from freenasUI.common.forms import ModelForm, Form
from freenasUI.freeadmin.views import JsonResp
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
    NFS_Share,
    NFS_Share_Path,
)
from freenasUI.storage.models import MountPoint, Volume, Scrub
from freenasUI.system import models

log = logging.getLogger('system.forms')
WIZARD_PROGRESSFILE = '/tmp/.initialwizard_progress'


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
    qs = MountPoint.objects.filter(mp_path=mp)
    if qs.exists():
        obj = qs[0]
        if not obj.mp_volume.is_decrypted():
            raise forms.ValidationError(
                _("The volume %s is locked by encryption") % (
                    obj.mp_volume.vol_name,
                )
            )


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


class InitialWizard(CommonWizard):

    template_done = 'system/initialwizard_done.html'

    def get_template_names(self):
        return [
            'system/initialwizard_%s.html' % self.steps.current,
            'system/initialwizard.html',
            'system/wizard.html',
        ]

    def done(self, form_list, **kwargs):

        progress = {
            'step': 1,
            'indeterminate': True,
            'percent': 0,
        }

        with open(WIZARD_PROGRESSFILE, 'wb') as f:
            f.write(pickle.dumps(progress))

        cleaned_data = self.get_all_cleaned_data()
        volume_name = cleaned_data.get('volume_name')
        volume_type = cleaned_data.get('volume_type')
        shares = cleaned_data.get('formset-shares')

        form_list = self.get_form_list()
        volume_form = form_list['volume']

        with transaction.atomic():
            volume = Volume(
                vol_name=volume_name,
                vol_fstype='ZFS',
            )
            volume.save()

            mp = MountPoint(
                mp_volume=volume,
                mp_path='/mnt/' + volume_name,
                mp_options='rw',
            )
            mp.save()

            bysize = volume_form._get_unused_disks_by_size()

            if volume_type == 'auto':
                groups = volume_form._grp_autoselect(bysize)
            else:
                groups = volume_form._grp_predefined(bysize, volume_type)

            _n = notifier()
            _n.init(
                "volume",
                volume,
                groups=groups,
                init_rand=False,
            )
            Scrub.objects.create(scrub_volume=volume)

            progress['step'] = 2
            progress['indeterminate'] = False
            progress['percent'] = 0
            with open(WIZARD_PROGRESSFILE, 'wb') as f:
                f.write(pickle.dumps(progress))

            services_restart = []
            for i, share in enumerate(shares):
                if not share:
                    continue

                share_name = share.get('share_name')
                share_purpose = share.get('share_purpose')
                share_allowguest = share.get('share_allowguest')
                share_timemachine = share.get('share_timemachine')
                share_iscsisize = share.get('share_iscsisize')
                share_user = share.get('share_user')
                share_usercreate = share.get('share_usercreate')
                share_userpw = share.get('share_userpw')
                share_group = share.get('share_group')
                share_groupcreate = share.get('share_groupcreate')
                share_mode = share.get('share_mode')

                if share_purpose != 'iscsitarget':
                    errno, errmsg = _n.create_zfs_dataset('%s/%s' % (
                        volume_name,
                        share_name
                    ), _restart_collectd=False)

                    qs = bsdGroups.objects.filter(bsdgrp_group=share_group)
                    if not qs.exists():
                        if not share_groupcreate:
                            raise MiddlewareError(
                                _('Group does not exist: %s') % share_group
                            )
                        gid = _n.group_create(share_group)
                        group = bsdGroups.objects.create(
                            bsdgrp_gid=gid,
                            bsdgrp_group=share_group,
                        )
                    else:
                        group = qs[0]

                    qs = bsdUsers.objects.filter(bsdusr_username=share_user)
                    if not qs.exists():
                        if not share_usercreate:
                            raise MiddlewareError(
                                _('User does not exist: %s') % share_user
                            )
                        if share_userpw:
                            password = share_userpw
                            password_disabled = False
                        else:
                            password = '!'
                            password_disabled = True
                        uid, gid, unixhash, smbhash = _n.user_create(
                            share_user,
                            share_user,
                            password,
                            password_disabled=password_disabled
                        )
                        bsdUsers.objects.create(
                            bsdusr_username=share_user,
                            bsdusr_full_name=share_user,
                            bsdusr_uid=uid,
                            bsdusr_group=group,
                            bsdusr_unixhash=unixhash,
                            bsdusr_smbhash=smbhash,
                        )

                    if share_purpose in ('cifs', 'afp'):
                        share_acl = 'windows'
                    else:
                        share_acl = 'unix'

                    _n.mp_change_permission(
                        path='/mnt/%s/%s' % (volume_name, share_name),
                        user=share_user,
                        group=share_group,
                        mode=share_mode,
                        recursive=False,
                        acl=share_acl,
                    )
                else:
                    errno, errmsg = _n.create_zfs_vol(
                        '%s/%s' % (volume_name, share_name),
                        share_iscsisize,
                        sparse=True,
                    )

                if errno > 0:
                    raise MiddlewareError(
                        _('Failed to create ZFS: %s') % errmsg
                    )

                path = '/mnt/%s/%s' % (volume_name, share_name)

                sharekwargs = {}

                if 'cifs' == share_purpose:
                    if share_allowguest:
                        sharekwargs['cifs_guestok'] = True
                    CIFS_Share.objects.create(
                        cifs_name=share_name,
                        cifs_path=path,
                        **sharekwargs
                    )

                if 'afp' == share_purpose:
                    if share_timemachine:
                        sharekwargs['afp_timemachine'] = True
                    AFP_Share.objects.create(
                        afp_name=share_name,
                        afp_path=path,
                        **sharekwargs
                    )

                if 'nfs' == share_purpose:
                    nfs_share = NFS_Share.objects.create(
                        nfs_comment=share_name,
                    )
                    NFS_Share_Path.objects.create(
                        share=nfs_share,
                        path=path,
                    )

                if 'iscsitarget' == share_purpose:

                    qs = iSCSITargetPortal.objects.all()
                    if qs.exists():
                        portal = qs[0]
                    else:
                        portal = iSCSITargetPortal.objects.create()
                        iSCSITargetPortalIP.objects.create(
                            iscsi_target_portalip_portal=portal,
                            iscsi_target_portalip_ip='0.0.0.0',
                        )

                    qs = iSCSITargetAuthorizedInitiator.objects.all()
                    if qs.exists():
                        authini = qs[0]
                    else:
                        authini = (
                            iSCSITargetAuthorizedInitiator.objects.create()
                        )
                    target = iSCSITarget.objects.create(
                        iscsi_target_name='%sTarget' % share_name,
                        iscsi_target_portalgroup=portal,
                        iscsi_target_initiatorgroup=authini,
                    )

                    iscsi_target_extent_path = 'zvol/%s/%s' % (
                        volume_name,
                        share_name,
                    )

                    extent = iSCSITargetExtent.objects.create(
                        iscsi_target_extent_name='%sExtent' % share_name,
                        iscsi_target_extent_type='ZVOL',
                        iscsi_target_extent_path=iscsi_target_extent_path,
                    )
                    iSCSITargetToExtent.objects.create(
                        iscsi_target=target,
                        iscsi_extent=extent,
                    )

                if share_purpose not in services_restart:
                    services.objects.filter(srv_service=share_purpose).update(
                        srv_enable=True
                    )
                    services_restart.append(share_purpose)

                progress['percent'] = int(
                    (float(i + 1) / float(len(shares))) * 100
                )
                with open(WIZARD_PROGRESSFILE, 'wb') as f:
                    f.write(pickle.dumps(progress))

        progress['step'] = 3
        progress['indeterminate'] = False
        progress['percent'] = 1
        with open(WIZARD_PROGRESSFILE, 'wb') as f:
            f.write(pickle.dumps(progress))

        # This must be outside transaction block to make sure the changes
        # are committed before the call of ix-fstab

        _n.reload("disk")  # Reloads collectd as well

        progress['percent'] = 50
        with open(WIZARD_PROGRESSFILE, 'wb') as f:
            f.write(pickle.dumps(progress))

        _n.start("ix-system")
        _n.start("ix-syslogd")
        _n.restart("system_datasets")  # FIXME: may reload collectd again

        progress['percent'] = 70
        with open(WIZARD_PROGRESSFILE, 'wb') as f:
            f.write(pickle.dumps(progress))

        _n.restart("cron")
        _n.reload("user")

        for service in services_restart:
            _n.restart(service)

        progress['percent'] = 100
        with open(WIZARD_PROGRESSFILE, 'wb') as f:
            f.write(pickle.dumps(progress))

        os.unlink(WIZARD_PROGRESSFILE)

        return JsonResp(
            self.request,
            message=__('Initial configuration succeeded.')
        )


class FirmwareWizard(FileWizard):

    def get_template_names(self):
        return [
            'system/firmware_wizard_%s.html' % self.get_step_index(),
        ]

    def done(self, form_list, **kwargs):
        cleaned_data = self.get_all_cleaned_data()
        firmware = cleaned_data.get('firmware')
        path = self.file_storage.path(firmware.file.name)

        # Verify integrity of uploaded image.
        assert ('sha256' in cleaned_data)
        checksum = notifier().checksum(path)
        if checksum != str(cleaned_data['sha256']).lower().strip():
            self.file_storage.delete(firmware.name)
            raise MiddlewareError("Invalid firmware, wrong checksum")

        # Validate that the image would pass all pre-install
        # requirements.
        #
        # IMPORTANT: pre-install step have scripts or executables
        # from the upload, so the integrity has to be verified
        # before we proceed with this step.
        try:
            retval = notifier().validate_update(path)
        except:
            self.file_storage.delete(firmware.name)
            raise

        if not retval:
            self.file_storage.delete(firmware.name)
            raise MiddlewareError("Invalid firmware")

        notifier().apply_update(path)
        try:
            notifier().destroy_upload_location()
        except Exception, e:
            log.warn("Failed to destroy upload location: %s", e.value)
        self.request.session['allow_reboot'] = True

        response = render_to_response('system/done.html', {
            'retval': getattr(self, 'retval', None),
        })
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
            self.instance._original_stg_guihttpsredirect != self.instance.stg_guihttpsredirect
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
            if self.instance._original_stg_guiprotocol == 'http':
                notifier().start_ssl("nginx")
            events.append("restartHttpd('%s')" % newurl)


class NTPForm(ModelForm):

    force = forms.BooleanField(label=_("Force"), required=False)

    class Meta:
        fields = '__all__'
        model = models.NTPServer

    def __init__(self, *args, **kwargs):
        super(NTPForm, self).__init__(*args, **kwargs)
        self.usable = True

    def clean_ntp_address(self):
        addr = self.cleaned_data.get("ntp_address")
        p1 = subprocess.Popen(
            ["/usr/sbin/ntpdate", "-q", addr],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        p1.communicate()
        if p1.returncode != 0:
            self.usable = False
        return addr

    def clean_ntp_maxpoll(self):
        maxp = self.cleaned_data.get("ntp_maxpoll")
        minp = self.cleaned_data.get("ntp_minpoll")
        if not maxp > minp:
            raise forms.ValidationError(_(
                "Max Poll should be higher than Min Poll"
            ))
        return maxp

    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("force", False) and not self.usable:
            self._errors['ntp_address'] = self.error_class([_(
                "Server could not be reached. Check \"Force\" to continue "
                "regardless."
            )])
            del cdata['ntp_address']
        return cdata

    def save(self):
        super(NTPForm, self).save()
        notifier().start("ix-ntpd")
        notifier().restart("ntpd")


class AdvancedForm(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.Advanced

    def __init__(self, *args, **kwargs):
        super(AdvancedForm, self).__init__(*args, **kwargs)
        self.instance._original_adv_motd = self.instance.adv_motd
        self.instance._original_adv_consolemenu = self.instance.adv_consolemenu
        self.instance._original_adv_powerdaemon = self.instance.adv_powerdaemon
        self.instance._original_adv_serialconsole = (
            self.instance.adv_serialconsole
        )
        self.instance._original_adv_consolescreensaver = (
            self.instance.adv_consolescreensaver
        )
        self.instance._original_adv_consolemsg = self.instance.adv_consolemsg
        self.instance._original_adv_advancedmode = (
            self.instance.adv_advancedmode
        )
        self.instance._original_adv_autotune = self.instance.adv_autotune
        self.instance._original_adv_debugkernel = self.instance.adv_debugkernel

    def save(self):
        super(AdvancedForm, self).save()
        loader_reloaded = False
        if self.instance._original_adv_motd != self.instance.adv_motd:
            notifier().start("motd")
        if self.instance._original_adv_consolemenu != self.instance.adv_consolemenu:
            notifier().start("ttys")
        if self.instance._original_adv_powerdaemon != self.instance.adv_powerdaemon:
            notifier().restart("powerd")
        if self.instance._original_adv_serialconsole != self.instance.adv_serialconsole:
            notifier().start("ttys")
            notifier().start("ix-sercons")
            if not loader_reloaded:
                notifier().reload("loader")
                loader_reloaded = True
        if self.instance._original_adv_consolescreensaver != self.instance.adv_consolescreensaver:
            if self.instance.adv_consolescreensaver == 0:
                notifier().stop("saver")
            else:
                notifier().start("saver")
            if not loader_reloaded:
                notifier().reload("loader")
                loader_reloaded = True
        if (
            self.instance._original_adv_autotune != self.instance.adv_autotune
            and not loader_reloaded
        ):
            notifier().reload("loader")
        if self.instance._original_adv_debugkernel != self.instance.adv_debugkernel:
            notifier().reload("loader")

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


class SSLForm(ModelForm):
    ssl_passphrase2 = forms.CharField(
        max_length=120,
        label=_("Confirm Passphrase"),
        widget=forms.widgets.PasswordInput(),
        required=False,
    )

    class Meta:
        fields = '__all__'
        model = models.SSL
        widgets = {
            'ssl_passphrase': forms.widgets.PasswordInput(render_value=False),
        }

    def __init__(self, *args, **kwargs):
        super(SSLForm, self).__init__(*args, **kwargs)
        self.fields.keyOrder = [
            'ssl_org',
            'ssl_unit',
            'ssl_email',
            'ssl_city',
            'ssl_state',
            'ssl_country',
            'ssl_common',
            'ssl_passphrase',
            'ssl_passphrase2',
            'ssl_certfile',
        ]
        if self.instance.ssl_passphrase:
            self.fields['ssl_passphrase'].required = False

    def clean_ssl_passphrase2(self):
        passphrase1 = self.cleaned_data.get("ssl_passphrase")
        passphrase2 = self.cleaned_data.get("ssl_passphrase2")
        if passphrase1 != passphrase2:
            raise forms.ValidationError(
                _("The two passphrase fields didn't match.")
            )
        return passphrase2

    def get_x509_modulus(self, x509_file_path):
        if not x509_file_path:
            return None

        proc = subprocess.Popen([
            "/usr/bin/openssl",
            "x509",
            "-noout",
            "-modulus",
            "-in", x509_file_path,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        modulus, err = proc.communicate()
        if proc.returncode != 0:
            return None

        return modulus.strip()

    def get_key_modulus(self, key_file_path, type='rsa'):
        if not key_file_path:
            return None

        proc = subprocess.Popen([
            "/usr/bin/openssl",
            type,
            "-noout",
            "-modulus",
            "-in", key_file_path,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        modulus, err = proc.communicate()
        if proc.returncode != 0:
            return None

        return modulus.strip()

    def clean_ssl_certfile(self):
        certfile = self.cleaned_data.get("ssl_certfile")
        if not certfile:
            return None
        reg = re.search(
            r'(-----BEGIN ([DR]SA) PRIVATE KEY-----.*?'
            r'-----END \2 PRIVATE KEY-----)',
            certfile,
            re.M | re.S
        )
        if not reg:
            raise forms.ValidationError(
                _("RSA or DSA private key not found")
            )
        priv = reg.group()

        priv_file = tempfile.mktemp(dir='/tmp/')
        with open(priv_file, 'w') as f:
            f.write(priv)

        keytype = None
        reg = re.search(r'-----BEGIN ([DR]SA) PRIVATE KEY-----', priv)
        if reg:
            keytype = reg.group(1).lower()

        modulus1 = self.get_key_modulus(priv_file, keytype)
        os.unlink(priv_file)
        if not modulus1:
            raise forms.ValidationError(
                _("RSA or DSA private key is not valid"))

        reg = re.findall(
            r'(-----BEGIN CERTIFICATE-----.*?'
            r'-----END CERTIFICATE-----)',
            certfile,
            re.M | re.S
        )

        verified = False
        for cert in reg:
            x509_file = tempfile.mktemp(dir='/tmp')
            with open(x509_file, 'w') as f:
                f.write(cert)

            modulus2 = self.get_x509_modulus(x509_file)
            os.unlink(x509_file)
            if modulus1 == modulus2:
                verified = True
                break

        if not verified:
            raise forms.ValidationError(
                _("The modulus of certificate and key must match")
            )

        return certfile

    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("ssl_passphrase2"):
            cdata['ssl_passphrase'] = cdata['ssl_passphrase2']
        return cdata

    def save(self):
        super(SSLForm, self).save()
        notifier().start_ssl("nginx")


class FirmwareTemporaryLocationForm(Form):
    mountpoint = forms.ChoiceField(
        label=_("Place to temporarily place firmware file"),
        help_text=_(
            "The system will use this place to temporarily store the "
            "firmware file before it's being applied."),
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
        super(FirmwareTemporaryLocationForm, self).__init__(*args, **kwargs)
        self.fields['mountpoint'].choices = [
            (x.mp_path, x.mp_path)
            for x in MountPoint.objects.exclude(mp_volume__vol_fstype='iscsi')
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


class FirmwareUploadForm(Form):
    firmware = FileField(label=_("New image to be installed"), required=True)
    sha256 = forms.CharField(
        label=_("SHA256 sum for the image"),
        required=True
    )


class ConfigUploadForm(Form):
    config = FileField(label=_("New config to be installed"))


"""
TODO: Move to a unittest .py file.

invalid_sysctls = [
    'a.0',
    'a.b',
    'a..b',
    'a._.b',
    'a.b._.c',
    '0',
    '0.a',
    'a-b',
    'a',
]

valid_sysctls = [
    'ab.0',
    'ab.b',
    'smbios.system.version',
    'dev.emu10kx.0.multichannel_recording',
    'hw.bce.tso0',
    'kern.sched.preempt_thresh',
    'net.inet.tcp.tso',
]

assert len(filter(SYSCTL_VARNAME_FORMAT_RE.match, invalid_sysctls)) == 0
assert len(
    filter(SYSCTL_VARNAME_FORMAT_RE.match, valid_sysctls)) == len(valid_sysctls
)
"""

# NOTE:
# - setenv in the kernel is more permissive than this, but we want to reduce
#   user footshooting.
# - this doesn't reject all benign input; it just rejects input that would
#   break system boots.
# XXX: note that I'm explicitly rejecting input for root sysctl nodes.
SYSCTL_TUNABLE_VARNAME_FORMAT = """Variable names must:
1. Start with a letter.
2. End with a letter or number.
3. Can contain a combination of alphanumeric characters, numbers, underscores,
   and/or periods.
"""
SYSCTL_VARNAME_FORMAT_RE = \
    re.compile('[a-z][a-z0-9_]+\.([a-z0-9_]+\.)*[a-z0-9_]+', re.I)

LOADER_VARNAME_FORMAT_RE = \
    re.compile('[a-z][a-z0-9_]+\.*([a-z0-9_]+\.)*[a-z0-9_]+', re.I)


class TunableForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.Tunable

    def clean_tun_comment(self):
        return self.cleaned_data.get('tun_comment').strip()

    def clean_tun_value(self):
        value = self.cleaned_data.get('tun_value')
        if '"' in value or "'" in value:
            raise forms.ValidationError(_('Quotes are not allowed'))
        return value

    def clean_tun_var(self):
        value = self.cleaned_data.get('tun_var').strip()
        qs = models.Tunable.objects.filter(tun_var=value)
        if self.instance.id:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise forms.ValidationError(_(
                'This variable already exists'
            ))
        return value

    def clean(self):
        cdata = self.cleaned_data
        value = cdata.get('tun_var')
        if value:
            if (
                cdata.get('tun_type') == 'loader' and
                not LOADER_VARNAME_FORMAT_RE.match(value)
            ) or (
                cdata.get('tun_type') == 'sysctl' and
                not SYSCTL_VARNAME_FORMAT_RE.match(value)
            ):
                self.errors['tun_var'] = self.error_class(
                    [_(SYSCTL_TUNABLE_VARNAME_FORMAT)]
                )
                cdata.pop('tun_var', None)
        return cdata

    def save(self):
        super(TunableForm, self).save()
        if self.cleaned_data.get('tun_type') == 'loader':
            notifier().reload("loader")
        else:
            notifier().reload("sysctl")


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


class SystemDatasetForm(ModelForm):
    sys_pool = forms.ChoiceField(
        label=_("System dataset pool"),
        required=False
    )

    class Meta:
        fields = '__all__'
        model = models.SystemDataset

    def __init__(self, *args, **kwargs):
        super(SystemDatasetForm, self).__init__(*args, **kwargs)
        pool_choices = [('', '')]
        for v in Volume.objects.all():
            pool_choices.append((v.vol_name, v.vol_name))

        self.fields['sys_pool'].choices = pool_choices
        self.instance._original_sys_pool = self.instance.sys_pool
        self.instance._original_sys_syslog_usedataset = self.instance.sys_syslog_usedataset
        self.instance._original_sys_rrd_usedataset = self.instance.sys_rrd_usedataset

    def save(self):
        super(SystemDatasetForm, self).save()
        if self.instance.sys_pool:
            try:
                notifier().system_dataset_create()
            except:
                raise MiddlewareError(_("Unable to create system dataset!"))
            if self.instance._original_sys_pool != self.instance.sys_pool:
                notifier().restart("system_datasets")

        if self.instance._original_sys_pool != self.instance.sys_pool:
            try:
                notifier().system_dataset_migrate(
                    self.instance._original_sys_pool, self.instance.sys_pool
                )
            except:
                raise MiddlewareError(_("Unable to migrate system dataset!"))

        if self.instance._original_sys_syslog_usedataset != self.instance.sys_syslog_usedataset:
            notifier().restart("syslogd")
        if self.instance._original_sys_rrd_usedataset != self.instance.sys_rrd_usedataset:
            notifier().restart("collectd")


class InitialWizardShareForm(Form):

    share_name = forms.CharField(
        label=_('Share Name'),
        max_length=80,
    )
    share_purpose = forms.ChoiceField(
        label=_('Purpose'),
        choices=(
            ('cifs', _('Windows (CIFS)')),
            ('afp', _('Apple (AFP)')),
            ('nfs', _('Unix (NFS)')),
            ('iscsitarget', _('Block Storage (iSCSI)')),
        ),
    )
    share_allowguest = forms.BooleanField(
        label=_('Allow Guest'),
        required=False,
    )
    share_timemachine = forms.BooleanField(
        label=_('Time Machine'),
        required=False,
    )
    share_iscsisize = forms.CharField(
        label=_('iSCSI Size'),
        max_length=255,
        required=False,
    )
    share_user = forms.CharField(
        max_length=100,
        required=False,
    )
    share_group = forms.CharField(
        max_length=100,
        required=False,
    )
    share_usercreate = forms.BooleanField(
        required=False,
    )
    share_userpw = forms.CharField(
        required=False,
        max_length=100,
    )
    share_groupcreate = forms.BooleanField(
        required=False,
    )
    share_mode = forms.CharField(
        max_length=3,
        required=False,
    )


class SharesBaseFormSet(BaseFormSet):

    RE_FIELDS = re.compile(r'^shares-(\d+)-share_(.+)$')

    def data_to_store(self):
        """
        Returns an array suitable to use in the dojo memory store.
        """
        keys = defaultdict(dict)
        for key, val in self.data.items():
            reg = self.RE_FIELDS.search(key)
            if not reg:
                continue
            idx, name = reg.groups()
            keys[idx][name] = val

        return json.dumps(keys.values())

InitialWizardShareFormSet = formset_factory(
    InitialWizardShareForm,
    formset=SharesBaseFormSet,
)


class InitialWizardVolumeForm(Form):

    volume_name = forms.CharField(
        label=_('Pool Name'),
        max_length=200,
    )
    volume_type = forms.ChoiceField(
        label=_('Type'),
        choices=(),
        widget=forms.RadioSelect,
        initial='auto',
    )

    def __init__(self, *args, **kwargs):
        super(InitialWizardVolumeForm, self).__init__(*args, **kwargs)
        self.fields['volume_type'].choices = (
            (
                'auto',
                _('Automatic')
            ),
            (
                'raid10',
                _('VMWare (RAID 10: Good Reliability, Good Performance)')
            ),
            (
                'raidz2',
                _('Backups (RAID Z2: Best Reliability, Less Storage)')
            ),
            (
                'raidz1',
                _('Media (RAID Z1: Less Reliability, More Storage)')
            ),
            (
                'stripe',
                _('Logs (RAID 0: No Reliability, Max Performance / Storage)')
            ),
        )

        self.types_avail = self._types_avail(self._get_unused_disks_by_size())

    @staticmethod
    def _get_unused_disks():
        _n = notifier()
        disks = _n.get_disks()
        for volume in Volume.objects.all():
            for disk in volume.get_disks():
                disks.pop(disk, None)
        return disks

    @classmethod
    def _get_unused_disks_by_size(cls):
        disks = cls._get_unused_disks()
        bysize = defaultdict(list)
        for disk, attrs in disks.items():
            size = int(attrs['capacity'])
            # Some disks might have a few sectors of difference.
            # We still want to group them together.
            # This is not ideal but good enough for now.
            size = size - (size % 10000)
            bysize[size].append(disk)
        return bysize

    @staticmethod
    def _higher_disks_group(bysize):
        higher = (None, 0)
        for size, _disks in bysize.items():
            if len(_disks) > higher[1]:
                higher = (size, len(_disks))
        return higher

    def _types_avail(self, disks):
        types = []
        ndisks = self._higher_disks_group(disks)[1]
        if ndisks >= 4:
            types.extend(['raid10', 'raidz2'])
        if ndisks >= 3:
            types.append('raidz1')
        if ndisks > 0:
            types.extend(['auto', 'stripe'])
        return types

    @staticmethod
    def _grp_type(num):
        check = OrderedDict((
            ('mirror', lambda y: y == 2),
            (
                'raidz',
                lambda y: False if y < 3 else math.log(y - 1, 2) % 1 == 0
            ),
            (
                'raidz2',
                lambda y: False if y < 4 else math.log(y - 2, 2) % 1 == 0
            ),
            (
                'raidz3',
                lambda y: False if y < 5 else math.log(y - 3, 2) % 1 == 0
            ),
            ('stripe', lambda y: True),
        ))
        for name, func in check.items():
            if func(num):
                return name
        return 'stripe'

    @classmethod
    def _grp_autoselect(cls, disks):

        higher = cls._higher_disks_group(disks)
        groups = OrderedDict()
        grpid = 0

        for size, devs in [(higher[0], disks[higher[0]])]:
            num = len(devs)
            if num in (4, 8):
                mod = 0
                perrow = num / 2
                rows = 2
                vdevtype = cls._grp_type(num / 2)
            elif num < 12:
                mod = 0
                perrow = num
                rows = 1
                vdevtype = cls._grp_type(num)
            elif num < 18:
                mod = num % 2
                rows = 2
                perrow = (num - mod) / 2
                vdevtype = cls._grp_type(perrow)
            elif num < 99:
                div9 = int(num / 9)
                div10 = int(num / 10)
                mod9 = num % 9
                mod10 = num % 10

                if mod9 >= 0.75 * div9 and mod10 >= 0.75 * div10:
                    perrow = 9
                    rows = div9
                    mod = mod9
                else:
                    perrow = 10
                    rows = div10
                    mod = mod10

                vdevtype = cls._grp_type(perrow)
            else:
                perrow = num
                rows = 1
                vdevtype = 'stripe'
                mod = 0

            for i in range(rows):
                groups[grpid] = {
                    'type': vdevtype,
                    'disks': devs[i * perrow:perrow * (i + 1)],
                }
                grpid += 1
            if mod > 0:
                groups[grpid] = {
                    'type': 'spare',
                    'disks': devs[-mod:],
                }
                grpid += 1
        return groups

    @classmethod
    def _grp_predefined(cls, disks, grptype):

        higher = cls._higher_disks_group(disks)

        maindisks = disks[higher[0]]

        groups = OrderedDict()
        grpid = 0

        if grptype == 'raid10':
            for i in range(len(maindisks) / 2):
                groups[grpid] = {
                    'type': 'mirror',
                    'disks': maindisks[i * 2:2 * (i + 1)],
                }
                grpid += 1
        else:
            groups[grpid] = {
                'type': grptype,
                'disks': maindisks,

            }

        return groups

    def _get_disk_size(self, disk, bysize):
        size = None
        for _size, disks in bysize.items():
            if disk in disks:
                size = _size
                break
        return size

    def _groups_to_size(self, bysize, groups, swapsize):
        size = 0
        for group in groups.values():
            lower = None
            for disk in group['disks']:
                _size = self._get_disk_size(disk, bysize)
                if _size and (not lower or lower > _size):
                    lower = _size - swapsize
            if not lower:
                continue

            if group['type'] == 'mirror':
                size += lower
            elif group['type'] == 'raidz1':
                size += lower * (len(group['disks']) - 1)
            elif group['type'] == 'raidz2':
                size += lower * (len(group['disks']) - 2)
            elif group['type'] == 'stripe':
                size += lower * len(group['disks'])
        return humanize_size(size)

    def choices_size(self):
        swapsize = models.Advanced.objects.order_by('-id')[0].adv_swapondrive
        swapsize *= 1024 * 1024 * 1024
        types = defaultdict(dict)
        bysize = self._get_unused_disks_by_size()
        for _type, descr in self.fields['volume_type'].choices:
            if _type == 'auto':
                groups = self._grp_autoselect(bysize)
            else:
                groups = self._grp_predefined(bysize, _type)
            types[_type] = self._groups_to_size(bysize, groups, swapsize)
        return json.dumps(types)

    def clean_volume_name(self):
        volume_name = self.cleaned_data.get('volume_name')
        if not volume_name:
            return volume_name
        qs = Volume.objects.filter(vol_name=volume_name)
        if qs.exists():
            raise forms.ValidationError(
                _("A pool with this name already exists.")
            )
        return volume_name

    def clean(self):
        volume_type = self.cleaned_data.get('volume_type')
        if not volume_type:
            self._errors['volume_type'] = self.error_class([
                _('No available disks have been found.'),
            ])
        return self.cleaned_data


class InitialWizardConfirmForm(Form):
    pass
