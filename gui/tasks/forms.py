from collections import OrderedDict
from datetime import time
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


RCLONE_MAP = OrderedDict((
    ('G', 1073741824.0),
    ('M', 1048576.0),
    ('k', 1024.0),
    ('b', 1),
))


def humanize_size_rclone(number):
    number = int(number)
    for suffix, factor in list(RCLONE_MAP.items()):
        if number % factor == 0:
            return '%d%s' % (number / factor, suffix)


class CloudSyncForm(ModelForm):

    attributes = forms.CharField(
        widget=CloudSyncWidget(),
        label=_('Provider'),
    )
    bwlimit = forms.CharField(
        label=_('Bandwidth limit'),
        help_text=_('Either single bandwidth limit or bandwidth limit schedule in rclone format.<br />'
                    'Example: "08:00,512 12:00,10M 13:00,512 18:00,30M 23:00,off".<br />'
                    'Default unit is kilobytes.')
    )
    exclude = forms.CharField(
        label=_('Exclude'),
        help_text=_('Newline-separated list of files and directories to exclude from sync.<br />'
                    'See https://rclone.org/filtering/ for more details on --exclude option.'),
        widget=forms.Textarea(),
    )

    class Meta:
        exclude = ('credential', 'args')
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
        if "instance" in kwargs:
            kwargs.setdefault("initial", {})
            try:
                kwargs["initial"]["encryption_password"] = notifier().pwenc_decrypt(
                    kwargs["instance"].encryption_password)
            except Exception:
                pass
            try:
                kwargs["initial"]["encryption_salt"] = notifier().pwenc_decrypt(kwargs["instance"].encryption_salt)
            except Exception:
                pass

            if len(kwargs["instance"].bwlimit) == 1 and kwargs["instance"].bwlimit[0]["time"] == "00:00":
                kwargs["initial"]["bwlimit"] = humanize_size_rclone(kwargs["instance"].bwlimit[0]['bandwidth'])
            else:
                kwargs["initial"]["bwlimit"] = " ".join([
                    f"{limit['time']},{humanize_size_rclone(limit['bandwidth']) if limit['bandwidth'] else 'off'}"
                    for limit in kwargs["instance"].bwlimit
                ])

            kwargs["initial"]["exclude"] = "\n".join(kwargs["instance"].exclude)

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

        self.fields['direction'].widget.attrs['onChange'] = (
            "cloudSyncDirectionToggle();"
        )

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

    def clean_bwlimit(self):
        v = self.cleaned_data.get('bwlimit')
        if "," not in v:
            v = f"00:00,{v}"

        bwlimit = []
        for t in v.split():
            try:
                time_, bandwidth = t.split(",", 1)
            except ValueError:
                raise forms.ValidationError(_('Invalid value: %r') % t)

            try:
                h, m = time_.split(":", 1)
            except ValueError:
                raise forms.ValidationError(_('Invalid time: %r') % time_)

            try:
                time(int(h), int(m))
            except ValueError:
                raise forms.ValidationError(_('Invalid time: %r') % time_)

            if bandwidth == "off":
                bandwidth = None
            else:
                try:
                    bandwidth = int(bandwidth) * 1024
                except ValueError:
                    try:
                        bandwidth = int(bandwidth[:-1]) * {
                            "b": 1, "k": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024}[bandwidth[-1]]
                    except (KeyError, ValueError):
                        raise forms.ValidationError(_('Invalid bandwidth: %r') % bandwidth)

            bwlimit.append({
                "time": time_,
                "bandwidth": bandwidth,
            })

        for a, b in zip(bwlimit, bwlimit[1:]):
            if a["time"] >= b["time"]:
                raise forms.ValidationError(_('Invalid time order: %s, %s') % (a["time"], b["time"]))

        return bwlimit

    def clean_exclude(self):
        return list(filter(None, map(lambda s: s.strip(), self.cleaned_data.get('exclude').split('\n'))))

    def save(self, **kwargs):
        with client as c:
            cdata = self.cleaned_data
            cdata['credentials'] = cdata['attributes'].pop('credential')
            cdata['schedule'] = {
                'minute': cdata.pop('minute'),
                'hour': cdata.pop('hour'),
                'dom': cdata.pop('daymonth'),
                'month': cdata.pop('month'),
                'dow': cdata.pop('dayweek')
            }
            if self.instance.id:
                c.call('cloudsync.update', self.instance.id, cdata)
            else:
                self.instance = models.CloudSync.objects.get(pk=c.call('cloudsync.create', cdata)['id'])
        return self.instance

    def delete(self, **kwargs):
        with client as c:
            c.call('cloudsync.delete', self.instance.id)


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
        update['month'] = self.cleaned_data.get("rsync_month")
        update['dayweek'] = self.cleaned_data.get("rsync_dayweek")
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
        return ",".join(self.data.getlist("smarttest_month"))

    def clean_smarttest_dayweek(self):
        return ",".join(self.data.getlist("smarttest_dayweek"))
