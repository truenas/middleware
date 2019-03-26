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
                    'If blank, then the default OU is used during computer account creation. '
                    'Precreate the computer account in a specific OU. The OU string '
                    'read from top to bottom without RDNs and delimited by a "/". '
                    'E.g. "createcomputer=Computers/Servers/Unix NB: A backslash '
                    '"\" is used as escape at multiple levels and may need to be '
                    'doubled or even quadrupled. It is not used as a separator.'
                )
            )
        ),
    ]
