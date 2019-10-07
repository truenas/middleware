import datetime
import json

from sqlalchemy import (
    Table, Column as _Column, ForeignKey, Index,
    Boolean, CHAR, DateTime, Integer, SmallInteger, String, Text,
)  # noqa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship  # noqa
from sqlalchemy.types import UserDefinedType

from middlewared.plugins.pwenc import encrypt, decrypt


def django_ix(index, table):
    django_indexes = {
        "ix_account_bsdusers_bsdusr_group_id": "account_bsdusers_30f2801f",
        "ix_directoryservice_activedirectory_ad_certificate_id": "directoryservice_activedirectory_a4250fac",
        "ix_directoryservice_activedirectory_ad_kerberos_realm_id": "directoryservice_activedirectory_b03e01d8",
        "ix_directoryservice_idmap_ldap_idmap_ldap_certificate_id": "directoryservice_idmap_ldap_592ad9d0",
        "ix_directoryservice_idmap_rfc2307_idmap_rfc2307_certificate_id": "directoryservice_idmap_rfc2307_869bf111",
        "ix_directoryservice_ldap_ldap_kerberos_realm_id": "directoryservice_ldap_9a19be3d",
        "ix_directoryservice_ldap_ldap_certificate_id": "directoryservice_ldap_c6ef382f",
        "ix_django_session_expire_date": "django_session_b7b81f0c",
        "ix_network_alias_alias_interface_id": "network_alias_5f318ef4",
        "ix_network_lagginterfacemembers_lagg_interfacegroup_id": "network_lagginterfacemembers_14f52ba0",
        "ix_plugins_kmod_plugin_id": "plugins_kmod_c01cad29",
        "ix_services_fibrechanneltotarget_fc_target_id": "services_fiberchanneltotarget_1d6856ca",
        "ix_services_ftp_ftp_ssltls_certificate_id": "services_ftp_f897b229",
        "ix_services_iscsitargetgroups_iscsi_target_initiatorgroup_id": "services_iscsitargetgroups_39e2d7df",
        "ix_services_iscsitargetgroups_iscsi_target_id": "services_iscsitargetgroups_c939c4d7",
        "ix_services_iscsitargetgroups_iscsi_target_portalgroup_id": "services_iscsitargetgroups_dcc120ea",
        "ix_services_iscsitargetportalip_iscsi_target_portalip_portal_id": "services_iscsitargetportalip_fe35c684",
        "ix_services_iscsitargettoextent_iscsi_target_id": "services_iscsitargettoextent_74972900",
        "ix_services_iscsitargettoextent_iscsi_extent_id": "services_iscsitargettoextent_8c3551d7",
        "ix_services_openvpnclient_client_certificate_id": "services_openvpnclient_337326e2",
        "ix_services_openvpnclient_root_ca_id": "services_openvpnclient_86125d3c",
        "ix_services_openvpnserver_root_ca_id": "services_openvpnserver_86125d3c",
        "ix_services_openvpnserver_server_certificate_id": "services_openvpnserver_94e62f0b",
        "ix_services_s3_s3_certificate_id": "services_s3_3f8aa88e",
        "ix_sharing_cifs_share_cifs_storage_task_id": "sharing_cifs_share_d7a6a3ae",
        "ix_storage_mountpoint_mp_volume_id": "storage_mountpoint_6b5c36c4",
        "ix_storage_replication_repl_ssh_credentials_id": "storage_replication_d46a5b35",
        "ix_system_acmeregistrationbody_acme_id": "system_acmeregistrationbody_1ece6752",
        "ix_system_advanced_adv_syslog_tls_certificate_id": "system_advanced_64258e8d",
        "ix_system_certificate_cert_acme_id": "system_certificate_8dc6a655",
        "ix_system_certificate_cert_signedby_id": "system_certificate_c172260b",
        "ix_system_certificateauthority_cert_signedby_id": "system_certificateauthority_c172260b",
        "ix_system_settings_stg_guicertificate_id": "system_settings_cf5c60c6",
        "ix_tasks_cloudsync_credential_id": "tasks_cloudsync_3472cfe9",
        "ix_vm_device_vm_id": "vm_device_0e0cecb8",
    }

    name = "ix_" + "_".join([table.name] + [column.name for column in index.columns])
    return django_indexes.get(name, name)


Model = declarative_base()
Model.metadata.naming_convention = {
    "django_ix": django_ix,
    "ix": "%(django_ix)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}


class Column(_Column):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("nullable", False)
        super().__init__(*args, **kwargs)


class JSON(UserDefinedType):
    def __init__(self, type=dict, encrypted=False):
        self.type = type
        self.encrypted = encrypted

    def get_col_spec(self, **kw):
        return "TEXT"

    def _bind_processor(self, value):
        result = json.dumps(value or self.type())
        if self.encrypted:
            result = encrypt(result)
        return result

    def bind_processor(self, dialect):
        return self._bind_processor

    def _result_processor(self, value):
        try:
            if self.encrypted:
                value = decrypt(value, _raise=True)
            return json.loads(value)
        except Exception:
            return self.type()

    def result_processor(self, dialect, coltype):
        return self._result_processor


class MultiSelectField(UserDefinedType):
    def get_col_spec(self, **kw):
        return "TEXT"

    def _bind_processor(self, value):
        if value is None:
            return None

        return ",".join(value)

    def bind_processor(self, dialect):
        return self._bind_processor

    def _result_processor(self, value):
        if value:
            try:
                return value.split(",")
            except Exception:
                pass

        return []

    def result_processor(self, dialect, coltype):
        return self._result_processor


class Time(UserDefinedType):
    def get_col_spec(self, **kw):
        return "TIME"

    def _bind_processor(self, value):
        if value is None:
            return None

        return value.isoformat()

    def bind_processor(self, dialect):
        return self._bind_processor

    def _result_processor(self, value):
        try:
            return datetime.time(*map(int, value.split(":")))
        except Exception:
            return datetime.time()

    def result_processor(self, dialect, coltype):
        return self._result_processor
