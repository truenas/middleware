#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from django.forms import FileField
from django.conf import settings
from django.contrib.formtools.wizard import FormWizard
from django.shortcuts import render_to_response
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.http import Http404

from freeadmin.forms import CronMultiple
from freenasUI.storage.models import MountPoint
from freenasUI.common.forms import ModelForm, Form
from freenasUI.system import models
from freenasUI.middleware.notifier import notifier
from dojango import forms
import choices

class FileWizard(FormWizard):
    @method_decorator(csrf_protect)
    def __call__(self, request, *args, **kwargs):
        """
        IMPORTANT
        This method was stolen from FormWizard.__call__

        This was necessary because the original code doesn't accept File Upload
        The reason of this is because there is no clean way to hold the information
        of an uploaded file across steps

        Also, an extra context is used to set the ajax post path/url
        """
        if 'extra_context' in kwargs:
            self.extra_context.update(kwargs['extra_context'])
        self.extra_context.update({'postpath': request.path})
        current_step = self.determine_step(request, *args, **kwargs)
        self.parse_params(request, *args, **kwargs)
        previous_form_list = []
        for i in range(current_step):
            f = self.get_form(i, request.POST, request.FILES)
            if not self._check_security_hash(request.POST.get("hash_%d" % i, ''),
                                             request, f):
                return self.render_hash_failure(request, i)

            if not f.is_valid():
                return self.render_revalidation_failure(request, i, f)
            else:
                self.process_step(request, f, i)
                previous_form_list.append(f)
        if request.method == 'POST':
            form = self.get_form(current_step, request.POST, request.FILES)
        else:
            form = self.get_form(current_step)
        if form.is_valid():
            self.process_step(request, form, current_step)
            next_step = current_step + 1

            if next_step == self.num_steps():
                return self.done(request, previous_form_list + [form])
            else:
                form = self.get_form(next_step)
                self.step = current_step = next_step

        return self.render(form, request, current_step)
    def get_form(self, step, data=None, files=None):
        """
        This is also required to pass request.FILES to the form
        """
        if files is not None:
            if step >= self.num_steps():
                raise Http404('Step %s does not exist' % step)
            return self.form_list[step](data, files, prefix=self.prefix_for_step(step), initial=self.initial.get(step, None))
        else:
            return super(FileWizard, self).get_form(step, data)
    def done(self, request, form_list):
        response = render_to_response('system/done.html', {
            #'form_list': form_list,
            'retval': getattr(self, 'retval', None),
        })
        if not request.is_ajax():
            response.content = "<html><body><textarea>"+response.content+"</textarea></boby></html>"
        return response
    def get_template(self, step):
        """
        TODO: templates as parameter
        """
        return ['system/wizard_%s.html' % step, 'system/wizard.html']
    def process_step(self, request, form, step):
        super(FileWizard, self).process_step(request, form, step)
        """
        We execute the form done method if there is one, for each step
        """
        if hasattr(form, 'done'):
            retval = form.done()
            if step == self.num_steps()-1:
                self.retval = retval

    def render_template(self, request, *args, **kwargs):
        response = super(FileWizard, self).render_template(request, *args, **kwargs)
        # This is required for the workaround dojo.io.frame for file upload
        if not request.is_ajax():
            response.content = "<html><body><textarea>"+response.content+"</textarea></boby></html>"
        return response
    def __init__(self, form_list, prefix="", initial=None):
        super(FileWizard, self).__init__(form_list, initial)
        self.saved_prefix = prefix
    def prefix_for_step(self, step):
        "Given the step, returns a Form prefix to use."
        return '%s%s' % (self.saved_prefix, str(step))

class SettingsForm(ModelForm):
    class Meta:
        model = models.Settings
        widgets = {
            'stg_timezone': forms.widgets.FilteringSelect(),
            'stg_language': forms.widgets.FilteringSelect(),
        }
    def __init__(self, *args, **kwargs):
        super(SettingsForm, self).__init__( *args, **kwargs)
        self.instance._original_stg_guiprotocol = self.instance.stg_guiprotocol
        self.instance._original_stg_guiaddress = self.instance.stg_guiaddress
        self.instance._original_stg_guiport = self.instance.stg_guiport
        self.instance._original_stg_syslogserver = self.instance.stg_syslogserver
        self.fields['stg_language'].choices=settings.LANGUAGES
        self.fields['stg_language'].label = _("Language (Require UI reload)")
        self.fields['stg_guiaddress'].choices = choices.IPChoices()
    def clean_stg_guiport(self):
        val = self.cleaned_data.get("stg_guiport")
        if val == '':
            return val
        try:
            val = int(val)
            if val < 1 or val > 65535:
                raise forms.ValidationError(_("You must specify a number between 1 and 65535, inclusive."))
        except ValueError:
            raise forms.ValidationError(_("Number is required."))
        print val
        return val
    def save(self):
        super(SettingsForm, self).save()
        if self.instance._original_stg_guiprotocol != self.instance.stg_guiprotocol or \
            self.instance._original_stg_guiaddress != self.instance.stg_guiaddress or \
            self.instance._original_stg_guiport != self.instance.stg_guiport:
            notifier().restart("http")
        if self.instance._original_stg_syslogserver != self.instance.stg_syslogserver:
            notifier().restart("syslogd")
        notifier().reload("timeservices")

class AdvancedForm(ModelForm):
    class Meta:
        exclude = ('adv_zeroconfbonjour', 'adv_tuning', 'adv_firmwarevc', 'adv_systembeep')
        model = models.Advanced
    def __init__(self, *args, **kwargs):
        super(AdvancedForm, self).__init__(*args, **kwargs) 
        self.instance._original_adv_motd = self.instance.adv_motd
        self.instance._original_adv_consolemenu = self.instance.adv_consolemenu
        self.instance._original_adv_powerdaemon = self.instance.adv_powerdaemon
        self.instance._original_adv_serialconsole = self.instance.adv_serialconsole
        self.instance._original_adv_consolescreensaver = self.instance.adv_consolescreensaver
    def save(self):
        super(AdvancedForm, self).save()
        if self.instance._original_adv_motd != self.instance.adv_motd:
            notifier().start("motd")
        if self.instance._original_adv_consolemenu != self.instance.adv_consolemenu:
            notifier().start("ttys")
        if self.instance._original_adv_powerdaemon != self.instance.adv_powerdaemon:
            notifier().restart("powerd")
        if self.instance._original_adv_serialconsole != self.instance.adv_serialconsole:
            notifier().start("ttys")
            notifier().start("loader")
        if self.instance._original_adv_consolescreensaver != self.instance.adv_consolescreensaver:
            if self.instance.adv_consolescreensaver == 0:
                notifier().stop("saver")
            else:
                notifier().start("saver")
            notifier().start("loader")


class EmailForm(ModelForm):
    em_pass1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput, required=False)
    em_pass2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput,
        help_text = _("Enter the same password as above, for verification."), required=False)
    class Meta:
        model = models.Email
        exclude = ('em_pass',)
    def __init__(self, *args, **kwargs):
        super(EmailForm, self).__init__( *args, **kwargs)
        try:
            self.fields['em_pass1'].initial = self.instance.em_pass
            self.fields['em_pass2'].initial = self.instance.em_pass
        except:
            pass
        self.fields['em_smtp'].widget.attrs['onChange'] = 'javascript:toggleEmail(this);'
        ro = True

        if len(self.data) > 0:
            if self.data.get("em_smtp", None) == "on":
                ro = False
        else:
            if self.instance.em_smtp == True:
                ro = False
        if ro:
            self.fields['em_user'].widget.attrs['disabled'] = 'disabled'
            self.fields['em_pass1'].widget.attrs['disabled'] = 'disabled' 
            self.fields['em_pass2'].widget.attrs['disabled'] = 'disabled' 

    def clean_em_user(self):
        if self.cleaned_data['em_smtp'] == True and \
                self.cleaned_data['em_user'] == "":
            raise forms.ValidationError(_("This field is required"))
        return self.cleaned_data['em_user']

    def clean_em_pass1(self):
        if self.cleaned_data['em_smtp'] == True and \
                self.cleaned_data['em_pass1'] == "":
            raise forms.ValidationError(_("This field is required"))
        return self.cleaned_data['em_pass1']
    def clean_em_pass2(self):
        if self.cleaned_data['em_smtp'] == True and \
                self.cleaned_data.get('em_pass2', "") == "":
            raise forms.ValidationError(_("This field is required"))
        pass1 = self.cleaned_data.get("em_pass1", "")
        pass2 = self.cleaned_data.get("em_pass2", "")
        if pass1 != pass2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return pass2
    def save(self, commit=True):
        email = super(EmailForm, self).save(commit=False)
        if commit:
            email.em_pass = self.cleaned_data['em_pass2']
            email.save()
            notifier().start("ix-msmtp")
        return email

class SSLForm(ModelForm):
    def save(self):
        super(SSLForm, self).save()
        notifier().start("ix-ssl")
    class Meta:
        model = models.SSL

class SMARTTestForm(ModelForm):
    def __init__(self, *args, **kwargs):
        if kwargs.has_key('instance'):
            ins = kwargs.get('instance')
            ins.smarttest_month = ins.smarttest_month.replace("10", "a").replace("11", "b").replace("12", "c")
            if ins.smarttest_daymonth == "..":
                ins.smarttest_daymonth = '*/1'
            if ins.smarttest_hour == "..":
                ins.smarttest_hour = '*/1'
        super(SMARTTestForm, self).__init__(*args, **kwargs)
    def save(self):
        super(SMARTTestForm, self).save()
        notifier().restart("smartd")
    def clean_smarttest_hour(self):
        h = self.cleaned_data.get("smarttest_hour")
        if h.startswith('*/'):
            each = int(h.split('*/')[1])
            if each == 1:
                return ".."
            else:
                minutes = []
                for i in range(24):
                    if i % each == 0:
                        minutes.append("%.2d" % i)
                return ",".join(minutes)
        return h
    def clean_smarttest_daymonth(self):
        h = self.cleaned_data.get("smarttest_daymonth")
        if h.startswith('*/'):
            each = int(h.split('*/')[1])
            if each == 1:
                return ".."
            else:
                days = []
                for i in range(1,32):
                    if i % each == 0:
                        days.append("%.2d" % i)
                return ",".join(days)
        return h
    def clean_smarttest_month(self):
        m = eval(self.cleaned_data.get("smarttest_month"))
        m = ",".join(m)
        m = m.replace("a", "10").replace("b", "11").replace("c", "12")
        return m
    def clean_smarttest_dayweek(self):
        w = eval(self.cleaned_data.get("smarttest_dayweek"))
        w = ",".join(w)
        return w
    class Meta:
        model = models.SMARTTest
        widgets = {
            'smarttest_hour': CronMultiple(attrs={'numChoices': 24,'label':_("hour")}),
            'smarttest_daymonth': CronMultiple(attrs={'numChoices': 31,'start':1,'label':_("day of month")}),
            'smarttest_dayweek': forms.CheckboxSelectMultiple(choices=choices.WEEKDAYS_CHOICES),
            'smarttest_month': forms.CheckboxSelectMultiple(choices=choices.MONTHS_CHOICES),
        }

class FirmwareTemporaryLocationForm(Form):
    mountpoint = forms.ChoiceField(label=_("Place to temporarily place firmware file"), help_text = _("The system will use this place to temporarily store the firmware file before it's being applied."),choices=(), widget=forms.Select(attrs={ 'class': 'required' }),)
    def __init__(self, *args, **kwargs):
        super(FirmwareTemporaryLocationForm, self).__init__(*args, **kwargs)
        self.fields['mountpoint'].choices = [(x.mp_path, x.mp_path) for x in MountPoint.objects.exclude(mp_volume__vol_fstype='iscsi')]
    def done(self):
        notifier().change_upload_location(self.cleaned_data["mountpoint"].__str__())

class FirmwareUploadForm(Form):
    firmware = FileField(label=_("New image to be installed"))
    sha256 = forms.CharField(label=_("SHA256 sum for the image"))
    def clean(self):
        cleaned_data = self.cleaned_data
        filename = '/var/tmp/firmware/firmware.xz'
        fw = open(filename, 'wb+')
        if cleaned_data.get('firmware'):
            for c in cleaned_data['firmware'].chunks():
                fw.write(c)
            fw.close()
            checksum = notifier().checksum(filename)
            retval = notifier().validate_xz(filename)
            if checksum != cleaned_data['sha256'].__str__().strip() or retval == False:
                msg = _(u"Invalid firmware or checksum")
                self._errors["firmware"] = self.error_class([msg])
                del cleaned_data["firmware"]
        else:
            self._errors["firmware"] = self.error_class([_("This field is required.")])
        return cleaned_data
    def done(self):
        notifier().update_firmware('/var/tmp/firmware/firmware.xz')

class ServicePackUploadForm(Form):
    servicepack = FileField(label=_("Service Pack image to be installed"))
    sha256 = forms.CharField(label=_("SHA256 sum for the image"))
    def clean(self):
        cleaned_data = self.cleaned_data
        filename = '/var/tmp/firmware/servicepack.txz'
        fw = open(filename, 'wb+')
        if cleaned_data.get('servicepack'):
            for c in cleaned_data['servicepack'].chunks():
                fw.write(c)
            fw.close()
            checksum = notifier().checksum(filename)
            retval = notifier().validate_xz(filename)
            if checksum != cleaned_data['sha256'].__str__() or retval == False:
                msg = _(u"Invalid service pack or checksum")
                self._errors["servicepack"] = self.error_class([msg])
                del cleaned_data["servicepack"]
        else:
            self._errors["servicepack"] = self.error_class([_("This field is required.")])
        return cleaned_data
    def done(self):
        return notifier().apply_servicepack()

class ConfigUploadForm(Form):
    config = FileField(label=_("New config to be installed"))

class CronJobForm(ModelForm):
    class Meta:
        model = models.CronJob
        widgets = {
            'cron_minute': CronMultiple(attrs={'numChoices': 60,'label':_("minute")}),
            'cron_hour': CronMultiple(attrs={'numChoices': 24,'label':_("hour")}),
            'cron_daymonth': CronMultiple(attrs={'numChoices': 31,'start':1,'label':_("day of month")}),
            'cron_dayweek': forms.CheckboxSelectMultiple(choices=choices.WEEKDAYS_CHOICES),
            'cron_month': forms.CheckboxSelectMultiple(choices=choices.MONTHS_CHOICES),
        }
    def __init__(self, *args, **kwargs):
        if kwargs.has_key('instance'):
            ins = kwargs.get('instance')
            ins.cron_month = ins.cron_month.replace("10", "a").replace("11", "b").replace("12", "c")
        super(CronJobForm, self).__init__(*args, **kwargs)
    def clean_cron_month(self):
        m = eval(self.cleaned_data.get("cron_month"))
        m = ",".join(m)
        m = m.replace("a", "10").replace("b", "11").replace("c", "12")
        return m
    def clean_cron_dayweek(self):
        w = eval(self.cleaned_data.get("cron_dayweek"))
        w = ",".join(w)
        return w
    def save(self):
        super(CronJobForm, self).save()
        started = notifier().restart("cron")

class RsyncForm(ModelForm):
    class Meta:
        model = models.Rsync
        widgets = {
            'rsync_minute': CronMultiple(attrs={'numChoices': 60,'label':_("minute")}),
            'rsync_hour': CronMultiple(attrs={'numChoices': 24,'label':_("hour")}),
            'rsync_daymonth': CronMultiple(attrs={'numChoices': 31,'start':1,'label':_("day of month")}),
            'rsync_dayweek': forms.CheckboxSelectMultiple(choices=choices.WEEKDAYS_CHOICES),
            'rsync_month': forms.CheckboxSelectMultiple(choices=choices.MONTHS_CHOICES),
        }
    def __init__(self, *args, **kwargs):
        if kwargs.has_key('instance'):
            ins = kwargs.get('instance')
            ins.rsync_month = ins.rsync_month.replace("10", "a").replace("11", "b").replace("12", "c")
        super(RsyncForm, self).__init__(*args, **kwargs)
    def clean_rsync_month(self):
        m = eval(self.cleaned_data.get("rsync_month"))
        m = ",".join(m)
        m = m.replace("a", "10").replace("b", "11").replace("c", "12")
        return m
    def clean_rsync_dayweek(self):
        w = eval(self.cleaned_data.get("rsync_dayweek"))
        w = ",".join(w)
        return w
    def save(self):
        super(RsyncForm, self).save()
        started = notifier().restart("cron")
