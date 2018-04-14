import json
import logging

from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI import choices
from freenasUI.common.forms import ModelForm, mchoicefield
from freenasUI.freeadmin.forms import CronMultiple
from freenasUI.middleware.client import client
from freenasUI.middleware.form import MiddlewareModelForm
from freenasUI.middleware.notifier import notifier
from freenasUI.system.models import CloudCredentials
from freenasUI.tasks import models
from freenasUI.freeadmin.utils import key_order

from .widgets import CloudSyncWidget

log = logging.getLogger('tasks.forms')


class CloudSyncForm(ModelForm):

    attributes = forms.CharField(
        widget=CloudSyncWidget(),
        label=_('Provider'),
    )

    class Meta:
        exclude = ('credential', )
        fields = '__all__'
        model = models.CloudSync
        widgets = {
            'minute': CronMultiple(
                attrs={'numChoices': 60, 'label': _("minute")}
            ),
            'hour': CronMultiple(
                attrs={'numChoices': 24, 'label': _("hour")}
            ),
            'daymonth': CronMultiple(
                attrs={
                    'numChoices': 31, 'start': 1, 'label': _("day of month"),
                }
            ),
            'dayweek': forms.CheckboxSelectMultiple(
                choices=choices.WEEKDAYS_CHOICES
            ),
            'month': forms.CheckboxSelectMultiple(
                choices=choices.MONTHS_CHOICES
            ),
        }

    def __init__(self, *args, **kwargs):
        super(CloudSyncForm, self).__init__(*args, **kwargs)
        key_order(self, 2, 'attributes', instance=True)
        mchoicefield(self, 'month', [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
        ])
        mchoicefield(self, 'dayweek', [
            1, 2, 3, 4, 5, 6, 7
        ])
        if self.instance.id:
            self.fields['attributes'].initial = {
                'credential': self.instance.credential.id,
            }
            self.fields['attributes'].initial.update(self.instance.attributes)

    def clean_attributes(self):
        attributes = self.cleaned_data.get('attributes')
        try:
            attributes = json.loads(attributes)
        except ValueError:
            raise forms.ValidationError(_('Invalid provider details.'))

        credential = attributes.get('credential')
        if not credential:
            raise forms.ValidationError(_('This field is required.'))
        qs = CloudCredentials.objects.filter(id=credential)
        if not qs.exists():
            raise forms.ValidationError(_('Invalid credential.'))

        if not attributes.get('bucket'):
            raise forms.ValidationError(_('Bucket is required.'))

        direction = self.cleaned_data.get('direction')
        folder = attributes.get('folder').strip('/')
        if direction == 'PULL' and folder:
            with client as c:
                if not c.call('backup.is_dir', credential, attributes['bucket'], folder):
                    raise forms.ValidationError(_('Folder "%s" does not exist.') % folder)

        return attributes

    def clean_month(self):
        m = self.data.getlist('month')
        if len(m) == 12:
            return '*'
        m = ','.join(m)
        return m

    def clean_dayweek(self):
        w = self.data.getlist('dayweek')
        if w == '*':
            return w
        if len(w) == 7:
            return '*'
        w = ','.join(w)
        return w

    def save(self, **kwargs):
        with client as c:
            cdata = self.cleaned_data
            cdata['credential'] = cdata['attributes'].pop('credential')
            if self.instance.id:
                c.call('backup.update', self.instance.id, cdata)
            else:
                self.instance = models.CloudSync.objects.get(pk=c.call('backup.create', cdata))
        return self.instance

    def delete(self, **kwargs):
        with client as c:
            c.call('backup.delete', self.instance.id)


class CronJobForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = 'cron_'
    middleware_plugin = 'cronjob'
    middleware_attr_schema = 'cron_job'
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.CronJob
        widgets = {
            'cron_command': forms.widgets.TextInput(),
            'cron_minute': CronMultiple(
                attrs={'numChoices': 60, 'label': _("minute")}
            ),
            'cron_hour': CronMultiple(
                attrs={'numChoices': 24, 'label': _("hour")}
            ),
            'cron_daymonth': CronMultiple(
                attrs={
                    'numChoices': 31, 'start': 1, 'label': _("day of month"),
                }
            ),
            'cron_dayweek': forms.CheckboxSelectMultiple(
                choices=choices.WEEKDAYS_CHOICES
            ),
            'cron_month': forms.CheckboxSelectMultiple(
                choices=choices.MONTHS_CHOICES
            ),
        }

    def __init__(self, *args, **kwargs):
        super(CronJobForm, self).__init__(*args, **kwargs)
        mchoicefield(self, 'cron_month', [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
        ])
        mchoicefield(self, 'cron_dayweek', [
            1, 2, 3, 4, 5, 6, 7
        ])

    def clean_cron_month(self):
        m = self.data.getlist("cron_month")
        if len(m) == 12:
            return '*'
        else:
            return ','.join(m)

    def clean_cron_dayweek(self):
        w = self.data.getlist('cron_dayweek')
        if w == '*':
            return w
        if len(w) == 7:
            return '*'
        else:
            return ','.join(w)

    def middleware_clean(self, update):
        update['schedule'] = {
            'minute': update.pop('minute'),
            'hour': update.pop('hour'),
            'dom': update.pop('daymonth'),
            'month': update.pop('month'),
            'dow': update.pop('dayweek')
        }
        return update


class InitShutdownForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "ini_"
    middleware_attr_schema = "init_shutdown_script"
    middleware_plugin = "initshutdownscript"
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.InitShutdown

    def __init__(self, *args, **kwargs):
        super(InitShutdownForm, self).__init__(*args, **kwargs)
        self.fields['ini_type'].widget.attrs['onChange'] = (
            "initshutdownModeToggle();"
        )

    def middleware_clean(self, data):
        data["type"] = data["type"].upper()
        data["when"] = data["when"].upper()
        return data


class RsyncForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "rsync_"
    middleware_attr_schema = "rsync_task"
    middleware_plugin = "rsynctask"
    is_singletone = False

    rsync_validate_rpath = forms.BooleanField(
        initial=True,
        label=_("Validate Remote Path"),
        required=False,
        help_text=_(
            "This ensures Remote Path Validation."
            " Uncheck this if the remote machine"
            " is currently offline or beyond network reach."
            " And/Or you do not want validation to be done."
        ),
    )

    class Meta:

        fields = [
            'rsync_path',
            'rsync_user',
            'rsync_remotehost',
            'rsync_remoteport',
            'rsync_mode',
            'rsync_remotemodule',
            'rsync_remotepath',
            'rsync_validate_rpath',
            'rsync_direction',
            'rsync_desc',
            'rsync_minute',
            'rsync_hour',
            'rsync_daymonth',
            'rsync_month',
            'rsync_dayweek',
            'rsync_recursive',
            'rsync_times',
            'rsync_compress',
            'rsync_archive',
            'rsync_delete',
            'rsync_quiet',
            'rsync_preserveperm',
            'rsync_preserveattr',
            'rsync_delayupdates',
            'rsync_extra',
            'rsync_enabled'
        ]
        model = models.Rsync
        widgets = {
            'rsync_minute': CronMultiple(
                attrs={'numChoices': 60, 'label': _("minute")}
            ),
            'rsync_hour': CronMultiple(
                attrs={'numChoices': 24, 'label': _("hour")}
            ),
            'rsync_daymonth': CronMultiple(
                attrs={
                    'numChoices': 31, 'start': 1, 'label': _("day of month"),
                }
            ),
            'rsync_dayweek': forms.CheckboxSelectMultiple(
                choices=choices.WEEKDAYS_CHOICES
            ),
            'rsync_month': forms.CheckboxSelectMultiple(
                choices=choices.MONTHS_CHOICES
            ),
        }

    def __init__(self, *args, **kwargs):
        super(RsyncForm, self).__init__(*args, **kwargs)
        mchoicefield(self, 'rsync_month', [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
        ])
        mchoicefield(self, 'rsync_dayweek', [
            1, 2, 3, 4, 5, 6, 7
        ])
        self.fields['rsync_mode'].widget.attrs['onChange'] = (
            "rsyncModeToggle();"
        )

    def middleware_clean(self, update):
        update['month'] = self.data.getlist("rsync_month")
        update['dayweek'] = self.data.getlist("rsync_dayweek")
        update['extra'] = update["extra"].split()
        update['schedule'] = {
            'minute': update.pop('minute'),
            'hour': update.pop('hour'),
            'dom': update.pop('daymonth'),
            'month': update.pop('month'),
            'dow': update.pop('dayweek')
        }
        return update

    def clean_rsync_month(self):
        m = self.data.getlist("rsync_month")
        if len(m) == 12:
            return '*'
        m = ",".join(m)
        return m

    def clean_rsync_dayweek(self):
        w = self.data.getlist("rsync_dayweek")
        if len(w) == 7:
            return '*'
        w = ",".join(w)
        return w


class SMARTTestForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'smarttest_'
    middleware_plugin = 'smart.test'
    middleware_attr_schema = 'smart_test'
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.SMARTTest
        widgets = {
            'smarttest_hour': CronMultiple(
                attrs={'numChoices': 24, 'label': _("hour")}
            ),
            'smarttest_daymonth': CronMultiple(
                attrs={
                    'numChoices': 31, 'start': 1, 'label': _("day of month"),
                }
            ),
            'smarttest_dayweek': forms.CheckboxSelectMultiple(
                choices=choices.WEEKDAYS_CHOICES
            ),
            'smarttest_month': forms.CheckboxSelectMultiple(
                choices=choices.MONTHS_CHOICES
            ),
        }

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs:
            ins = kwargs.get('instance')
            if ins.smarttest_daymonth == "..":
                ins.smarttest_daymonth = '*/1'
            elif ',' in ins.smarttest_daymonth:
                days = [int(day) for day in ins.smarttest_daymonth.split(',')]
                gap = days[1] - days[0]
                everyx = list(range(0, 32, gap))[1:]
                if everyx == days:
                    ins.smarttest_daymonth = '*/%d' % gap
            if ins.smarttest_hour == "..":
                ins.smarttest_hour = '*/1'
            elif ',' in ins.smarttest_hour:
                hours = [int(hour) for hour in ins.smarttest_hour.split(',')]
                gap = hours[1] - hours[0]
                everyx = list(range(0, 24, gap))
                if everyx == hours:
                    ins.smarttest_hour = '*/%d' % gap
        super(SMARTTestForm, self).__init__(*args, **kwargs)
        key_order(self, 0, 'smarttest_disks', instance=True)
        mchoicefield(self, 'smarttest_month', [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
        ])
        mchoicefield(self, 'smarttest_dayweek', [
            1, 2, 3, 4, 5, 6, 7
        ])

    def middleware_clean(self, data):
        data['disks'] = [disk.pk for disk in data['disks']]
        test_type = {
            'L': 'LONG',
            'S': 'SHORT',
            'C': 'CONVEYANCE',
            'O': 'OFFLINE',
        }
        data['type'] = test_type[data['type']]
        data['schedule'] = {
            'hour': data.pop('hour'),
            'dom': data.pop('daymonth'),
            'month': data.pop('month'),
            'dow': data.pop('dayweek')
        }
        return data

    def clean_smarttest_hour(self):
        h = self.cleaned_data.get("smarttest_hour")
        if h.startswith('*/'):
            each = int(h.split('*/')[1])
            if each == 1:
                return ".."
        return h

    def clean_smarttest_daymonth(self):
        h = self.cleaned_data.get("smarttest_daymonth")
        if h.startswith('*/'):
            each = int(h.split('*/')[1])
            if each == 1:
                return ".."
        return h

    def clean_smarttest_month(self):
        m = eval(self.cleaned_data.get("smarttest_month"))
        m = ",".join(m)
        return m

    def clean_smarttest_dayweek(self):
        w = eval(self.cleaned_data.get("smarttest_dayweek"))
        w = ",".join(w)
        return w
