# encoding: utf-8
from south.db import db
from south.v2 import DataMigration


class Migration(DataMigration):

    def forwards(self, orm):

        # Adding model 'vcenterauxsettings'
        db.create_table(
            'vcp_vcenterauxsettings',
            (
                ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
                ('vc_enable_https', self.gf('django.db.models.fields.BooleanField')(default=False)),
            )
        )
        db.send_create_signal('vcp', ['vcenterauxsettings'])
        vcpaux = orm.vcenterauxsettings()
        vcpaux.vc_enable_https = False
        vcpaux.save()

    def backwards(self, orm):

        # Deleting model 'vcenterauxsettings'
        db.delete_table('vcp_vcenterauxsettings')

    models = {
        'vcp.vcenterauxsettings': {
            'Meta': {'object_name': 'VcenterAuxSettings'},
            'vc_enable_https': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
        }
    }

    complete_apps = ['vcp']
