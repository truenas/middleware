import django.core.validators
from django.db import migrations, models
import freenasUI.freeadmin.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('directoryservice', '0008__alter_kerberos_principal'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ActiveDirectory',
            name='ad_userdn',
        ),
        migrations.RemoveField(
            model_name='ActiveDirectory',
            name='ad_groupdn',
        ),
        migrations.RemoveField(
            model_name='ActiveDirectory',
            name='ad_dcname',
        ),
        migrations.RemoveField(
            model_name='ActiveDirectory',
            name='ad_gcname',
        ),
        migrations.RemoveField(
            model_name='ActiveDirectory',
            name='ad_enable_monitor',
        ),
        migrations.RemoveField(
            model_name='ActiveDirectory',
            name='ad_recover_retry',
        ),
        migrations.RemoveField(
            model_name='ActiveDirectory',
            name='ad_monitor_frequency',
        ),
        migrations.AddField(
            model_name='ActiveDirectory',
            name='ad_createcomputer',
            field=models.CharField(
                blank=True, 
                max_length=255, 
                verbose_name='Computer Account Organizational Unit',
                help_text=(
                    'When blank, the default Organizational Unit is used during computer account creation. '
                    'Precreate the computer account in a specific OU. The OU string '
                    'read from top to bottom without RDNs and delimited by a "/". '
                    'For example, "createcomputer=Computers/Servers/Unix NB: Use a backslash '
                    '"\" as escape at multiple levels. It is not used as a separator.'
                )
            )
        ),
    ]
