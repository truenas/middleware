import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
import importlib.util
import os
import sys

from mako import exceptions
from middlewared.plugins.account_.constants import CONTAINER_ROOT_UID
from middlewared.service import CallError, Service
from middlewared.utils.io import write_if_changed, FileChanges
from middlewared.utils.mako import get_template

DEFAULT_ETC_PERMS = 0o644
DEFAULT_ETC_XID = 0


class FileShouldNotExist(Exception):
    pass


class Checkpoint(StrEnum):
    """Boot-sequence checkpoints at which etc.generate_checkpoint() is called.

    An EtcEntry with checkpoint=None is skipped during checkpoint-triggered generation;
    it only renders when generate() is called directly without a checkpoint argument.
    """
    INITIAL = 'initial'
    INTERFACE_SYNC = 'interface_sync'
    POST_INIT = 'post_init'
    POOL_IMPORT = 'pool_import'
    PRE_INTERFACE_SYNC = 'pre_interface_sync'


class RendererType(StrEnum):
    """Renderer used to produce a config file's contents.

    MAKO renders a .mako template from etc_files/. PY executes a .py script from etc_files/ whose
    render() function returns the file contents as bytes or str, or None if the script writes the
    file itself (in which case change detection via write_if_changed is unavailable).
    """
    MAKO = 'mako'
    PY = 'py'


@dataclass(slots=True, frozen=True)
class CtxMethod:
    """A middleware method call whose result is shared across all renderers in an EtcGroup.

    method:     middleware method name passed to middleware.call().
    args:       positional arguments forwarded to the method call.
    ctx_prefix: when set, the result is stored in the context dict as '<ctx_prefix>.<method>'
                instead of '<method>', allowing the same method to appear multiple times with
                different args (e.g. nvmet.port.transport_address_choices for TCP and RDMA).
    """
    method: str
    args: list = field(default_factory=list)
    ctx_prefix: str | None = None


@dataclass(slots=True, frozen=True)
class EtcEntry:
    """A single config file to be generated.

    renderer_type: selects the renderer (mako template or python script).
    path:          output path written as /etc/<path>, with a leading 'local/' stripped.
                   also the source template path under etc_files/ unless local_path overrides it.
    local_path:    overrides the source template lookup path under etc_files/.
    checkpoint:    the boot checkpoint at which this entry is rendered; None means the entry is
                   only rendered when generate() is called without a checkpoint argument.
    mode:          octal permission bits applied to the output file.
    owner:         if set, the output file is chowned to this builtin username; otherwise uid 0.
    group:         if set, the output file is chgrped to this builtin group name; otherwise gid 0.
    """
    renderer_type: RendererType
    path: str
    local_path: str | None = None
    checkpoint: Checkpoint | None = Checkpoint.INITIAL
    mode: int = DEFAULT_ETC_PERMS
    owner: str | None = None
    group: str | None = None


@dataclass(slots=True, frozen=True)
class EtcGroup:
    """A named set of config files that share render context.

    entries: the config files to generate; rendered in order.
    ctx:     middleware calls executed once per generate() call; results are passed as a dict
             to every renderer in entries. Empty when no shared context is needed.
    """
    entries: tuple[EtcEntry, ...]
    ctx: tuple[CtxMethod, ...] = field(default_factory=tuple)


class MakoRenderer(object):

    def __init__(self, service):
        self.service = service

    async def render(self, path, ctx):
        try:
            # Mako is not asyncio friendly so run it within a thread
            def do():
                # Get the template by its relative path
                tmpl = get_template(os.path.relpath(path, os.path.dirname(os.path.dirname(__file__))) + ".mako")

                # Render the template
                return tmpl.render(
                    middleware=self.service.middleware,
                    service=self.service,
                    FileShouldNotExist=FileShouldNotExist,
                    render_ctx=ctx
                )

            return await self.service.middleware.run_in_thread(do)
        except FileShouldNotExist:
            raise
        except Exception:
            self.service.logger.debug('Failed to render mako template: {0}'.format(
                exceptions.text_error_template().render()
            ))
            raise


class PyRenderer(object):

    def __init__(self, service):
        self.service = service

    async def render(self, path, ctx):
        name = os.path.basename(path)
        filepath = f"{path}.py"

        spec = importlib.util.spec_from_file_location(name, filepath)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec for {name!r} from {filepath!r}")

        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            sys.modules.pop(name, None)
            raise

        args = [self.service, self.service.middleware]
        if ctx is not None:
            args.append(ctx)

        if asyncio.iscoroutinefunction(mod.render):
            return await mod.render(*args)
        else:
            return await self.service.middleware.run_in_thread(mod.render, *args)


class EtcService(Service):

    GROUPS: dict[str, EtcGroup] = {
        'audit': EtcGroup(
            ctx=(CtxMethod(method='system.security.config'),),
            entries=(
                EtcEntry(renderer_type=RendererType.PY, path='audit_setup'),
            ),
        ),
        'app_registry': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='docker/config.json'),
        )),
        'ctdb': EtcGroup(
            ctx=(
                CtxMethod(method='failover.licensed'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='ctdb/nodes'),
                EtcEntry(renderer_type=RendererType.MAKO, path='ctdb/ctdb.conf'),
            ),
        ),
        'docker': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='docker/daemon.json'),
        )),
        'truesearch': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='truesearch/config.json'),
        )),
        'webshare': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='webshare/config.json'),
            EtcEntry(renderer_type=RendererType.PY, path='webshare-auth/config.json'),
            EtcEntry(renderer_type=RendererType.PY, path='webshare-link/config.json'),
        )),
        'truenas_nvdimm': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='truenas_nvdimm', checkpoint=Checkpoint.POST_INIT),
        )),
        'shadow': EtcGroup(
            ctx=(
                CtxMethod(method='user.query', args=[[['local', '=', True], ['uid', '!=', CONTAINER_ROOT_UID]]]),
                CtxMethod(method='system.security.config'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='shadow', group='shadow', mode=0o0640),
            ),
        ),
        'user': EtcGroup(
            ctx=(
                CtxMethod(method='system.security.config'),
                CtxMethod(method='user.query', args=[[['local', '=', True], ['uid', '!=', CONTAINER_ROOT_UID]]]),
                CtxMethod(method='group.query', args=[[['local', '=', True]]]),
                CtxMethod(method='auth.twofactor.config'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='group'),
                EtcEntry(renderer_type=RendererType.MAKO, path='passwd', local_path='master.passwd'),
                EtcEntry(renderer_type=RendererType.MAKO, path='shadow', group='shadow', mode=0o0640),
                EtcEntry(renderer_type=RendererType.MAKO, path='local/sudoers', mode=0o440),
                EtcEntry(renderer_type=RendererType.MAKO, path='aliases', local_path='mail/aliases'),
                EtcEntry(renderer_type=RendererType.PY, path='web_ui_root_login_alert'),
                EtcEntry(renderer_type=RendererType.MAKO, path='subuid'),
                EtcEntry(renderer_type=RendererType.MAKO, path='subgid'),
                EtcEntry(renderer_type=RendererType.MAKO, path='local/users.oath',
                         mode=0o0600, checkpoint=Checkpoint.POOL_IMPORT),
            ),
        ),
        'netdata': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='netdata/netdata.conf', checkpoint=Checkpoint.POOL_IMPORT),
            EtcEntry(renderer_type=RendererType.MAKO,
                     path='netdata/charts.d/exclude_netdata.conf', checkpoint=Checkpoint.POOL_IMPORT),
            EtcEntry(renderer_type=RendererType.MAKO, path='netdata/go.d/upsd.conf'),
            EtcEntry(renderer_type=RendererType.MAKO, path='netdata/exporting.conf'),
        )),
        'fstab': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='fstab'),
            EtcEntry(renderer_type=RendererType.PY, path='fstab_configure', checkpoint=Checkpoint.POST_INIT),
        )),
        'ipa': EtcGroup(
            ctx=(
                CtxMethod(method='directoryservices.config'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.PY, path='ipa/default.conf'),
                EtcEntry(renderer_type=RendererType.PY, path='ipa/ca.crt'),
                EtcEntry(renderer_type=RendererType.PY, path='ipa/smb.keytab', mode=0o600),
            ),
        ),
        'kerberos': EtcGroup(
            ctx=(
                CtxMethod(method='directoryservices.status'),
                CtxMethod(method='kerberos.config'),
                CtxMethod(method='kerberos.realm.query'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.PY, path='krb5.conf', mode=0o644),
                EtcEntry(renderer_type=RendererType.PY, path='krb5.keytab', mode=0o600),
            ),
        ),
        'cron': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='cron.d/middlewared', checkpoint=Checkpoint.POOL_IMPORT),
        )),
        'grub': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='grub', checkpoint=Checkpoint.POST_INIT),
        )),
        'fips': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='fips', checkpoint=None),
        )),
        'keyboard': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='default/keyboard'),
            EtcEntry(renderer_type=RendererType.MAKO, path='vconsole.conf'),
        )),
        'ldap': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='local/openldap/ldap.conf'),
            EtcEntry(renderer_type=RendererType.MAKO, path='sssd/sssd.conf', mode=0o0600),
        )),
        'dhcpcd': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='dhcpcd.conf'),
        )),
        'nfsd': EtcGroup(
            ctx=(
                CtxMethod(method='sharing.nfs.query', args=[[('enabled', '=', True), ('locked', '=', False)]]),
                CtxMethod(method='nfs.config'),
                CtxMethod(method='system.global.id'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='nfs.conf'),
                EtcEntry(renderer_type=RendererType.MAKO, path='default/rpcbind'),
                EtcEntry(renderer_type=RendererType.MAKO, path='idmapd.conf'),
                EtcEntry(renderer_type=RendererType.MAKO, path='exports', checkpoint=Checkpoint.INTERFACE_SYNC),
            ),
        ),
        'nvmet': EtcGroup(
            ctx=(
                CtxMethod(method='failover.licensed'),
                CtxMethod(method='failover.node'),
                CtxMethod(method='failover.status'),
                CtxMethod(method='nvmet.global.ana_active'),
                CtxMethod(method='nvmet.global.ana_enabled'),
                CtxMethod(method='nvmet.global.config'),
                CtxMethod(method='nvmet.global.rdma_enabled'),
                CtxMethod(method='nvmet.host.query'),
                CtxMethod(method='nvmet.namespace.query'),
                CtxMethod(method='nvmet.port.query'),
                CtxMethod(method='nvmet.port.usage'),
                CtxMethod(method='nvmet.subsys.firmware'),
                CtxMethod(method='nvmet.subsys.model'),
                CtxMethod(method='nvmet.subsys.query'),
                CtxMethod(method='nvmet.host_subsys.query'),
                CtxMethod(method='nvmet.port_subsys.query'),
                CtxMethod(method='nvmet.port.transport_address_choices', args=['TCP', True], ctx_prefix='tcp'),
                CtxMethod(method='nvmet.port.transport_address_choices', args=['RDMA', True], ctx_prefix='rdma'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.PY, path='nvmet_kernel'),
                EtcEntry(renderer_type=RendererType.PY, path='nvmet_spdk'),
            ),
        ),
        'pam': EtcGroup(
            ctx=(
                CtxMethod(method='directoryservices.status'),
                CtxMethod(method='system.security.config'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/common-account'),
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/common-auth'),
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/common-auth-unix'),
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/common-password'),
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/common-session-noninteractive'),
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/common-session'),
                EtcEntry(renderer_type=RendererType.MAKO, path='security/pam_winbind.conf'),
                EtcEntry(renderer_type=RendererType.MAKO, path='security/limits.conf'),
            ),
        ),
        'pam_truenas': EtcGroup(
            ctx=(
                CtxMethod(method='datastore.config', args=['system.settings']),
                CtxMethod(method='system.security.config'),
                CtxMethod(method='auth.twofactor.config'),
                CtxMethod(method='api_key.query', args=[[['revoked', '=', False]]]),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/truenas'),
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/truenas-api-key'),
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/truenas-session'),
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/truenas-unix'),
                EtcEntry(renderer_type=RendererType.PY, path='pam_keyring'),
            ),
        ),
        'ftp': EtcGroup(
            ctx=(
                CtxMethod(method='ftp.config'),
                CtxMethod(method='user.query', args=[[['builtin', '=', True], ['username', '!=', 'ftp']]]),
                CtxMethod(method='network.configuration.config'),
                CtxMethod(method='directoryservices.config'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='proftpd/proftpd.conf'),
                EtcEntry(renderer_type=RendererType.MAKO, path='proftpd/proftpd.motd'),
                EtcEntry(renderer_type=RendererType.MAKO, path='proftpd/tls.conf'),
                EtcEntry(renderer_type=RendererType.MAKO, path='ftpusers'),
            ),
        ),
        'kdump': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='default/kdump-tools'),
        )),
        'rc': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='systemd'),
        )),
        'sysctl': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='sysctl.d/tunables.conf'),
        )),
        'ssl': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='generate_ssl_certs'),
        )),
        'scst': EtcGroup(
            ctx=(
                CtxMethod(method='failover.licensed'),
                CtxMethod(method='failover.node'),
                CtxMethod(method='failover.status'),
                CtxMethod(method='fc.capable'),
                CtxMethod(method='fcport.query'),
                CtxMethod(method='iscsi.auth.query'),
                CtxMethod(method='iscsi.extent.query', args=[[['enabled', '=', True]]]),
                CtxMethod(method='iscsi.global.alua_enabled'),
                CtxMethod(method='iscsi.global.config'),
                CtxMethod(method='iscsi.initiator.query'),
                CtxMethod(method='iscsi.portal.query'),
                CtxMethod(method='iscsi.target.query'),
                CtxMethod(method='iscsi.targetextent.query'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='scst.conf',
                         checkpoint=Checkpoint.POOL_IMPORT, mode=0o600),
                EtcEntry(renderer_type=RendererType.MAKO, path='scst.env',
                         checkpoint=Checkpoint.POOL_IMPORT, mode=0o744),
            ),
        ),
        'scst_direct': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='scst.direct',
                     checkpoint=Checkpoint.POOL_IMPORT, mode=0o600),
        )),
        'scst_targets': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='initiators.allow', checkpoint=Checkpoint.POOL_IMPORT),
            EtcEntry(renderer_type=RendererType.MAKO, path='initiators.deny', checkpoint=Checkpoint.POOL_IMPORT),
        )),
        'udev': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='udev'),
        )),
        'nginx': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='local/nginx/nginx.conf',
                     checkpoint=Checkpoint.INTERFACE_SYNC),
        )),
        'keepalived': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='keepalived/keepalived.conf',
                     group='root', mode=0o644, local_path='keepalived.conf'),
        )),
        'motd': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='motd'),
        )),
        'mdns': EtcGroup(
            ctx=(
                CtxMethod(method='interface.query'),
                CtxMethod(method='smb.config'),
                CtxMethod(method='ups.config'),
                CtxMethod(method='system.general.config'),
                CtxMethod(method='service.started_or_enabled', args=['cifs']),
                CtxMethod(method='service.started_or_enabled', args=['ups'], ctx_prefix='ups'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='local/avahi/avahi-daemon.conf', checkpoint=None),
                EtcEntry(renderer_type=RendererType.PY, path='local/avahi/services/ADISK.service', checkpoint=None),
                EtcEntry(renderer_type=RendererType.PY, path='local/avahi/services/DEV_INFO.service', checkpoint=None),
                EtcEntry(renderer_type=RendererType.PY, path='local/avahi/services/HTTP.service', checkpoint=None),
                EtcEntry(renderer_type=RendererType.PY, path='local/avahi/services/SMB.service', checkpoint=None),
                EtcEntry(renderer_type=RendererType.PY, path='local/avahi/services/nut.service', checkpoint=None),
            ),
        ),
        'nscd': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='nscd.conf'),
        )),
        'nss': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='nsswitch.conf'),
        )),
        'wsd': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='local/wsdd.conf', checkpoint=Checkpoint.POST_INIT),
        )),
        'ups': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='local/nut/ups_config'),
            EtcEntry(renderer_type=RendererType.MAKO, path='local/nut/ups.conf', owner='root', group='nut', mode=0o440),
            EtcEntry(renderer_type=RendererType.MAKO, path='local/nut/upsd.conf',
                     owner='root', group='nut', mode=0o440),
            EtcEntry(renderer_type=RendererType.MAKO, path='local/nut/upsd.users',
                     owner='root', group='nut', mode=0o440),
            EtcEntry(renderer_type=RendererType.MAKO, path='local/nut/upsmon.conf',
                     owner='root', group='nut', mode=0o440),
            EtcEntry(renderer_type=RendererType.MAKO, path='local/nut/upssched.conf',
                     owner='root', group='nut', mode=0o440),
            EtcEntry(renderer_type=RendererType.MAKO, path='local/nut/nut.conf', owner='root', group='nut', mode=0o440),
            EtcEntry(renderer_type=RendererType.PY, path='local/nut/ups_perms'),
        )),
        'smb': EtcGroup(
            ctx=(
                CtxMethod(method='smb.generate_smb_configuration'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='local/smb4.conf'),
            ),
        ),
        'snmpd': EtcGroup(entries=(
            EtcEntry(
                renderer_type=RendererType.MAKO, path='snmp/snmpd.conf',
                local_path='local/snmpd.conf', owner='root', group='Debian-snmp', mode=0o640,
            ),
        )),
        'syslogd': EtcGroup(
            ctx=(
                CtxMethod(method='system.advanced.config'),
                CtxMethod(method='nfs.config'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='syslog-ng/syslog-ng.conf'),
                EtcEntry(renderer_type=RendererType.MAKO, path='syslog-ng/conf.d/tndestinations.conf'),
                EtcEntry(renderer_type=RendererType.MAKO, path='syslog-ng/conf.d/tnfilters.conf'),
                EtcEntry(renderer_type=RendererType.MAKO, path='syslog-ng/conf.d/tnaudit.conf', mode=0o600),
            ),
        ),
        'hosts': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='hosts',
                     mode=0o644, checkpoint=Checkpoint.PRE_INTERFACE_SYNC),
        )),
        'hostname': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='hostname', checkpoint=Checkpoint.PRE_INTERFACE_SYNC),
        )),
        'ssh': EtcGroup(
            ctx=(
                CtxMethod(method='ssh.config'),
                CtxMethod(method='auth.twofactor.config'),
                CtxMethod(method='interface.query'),
                CtxMethod(method='system.advanced.login_banner'),
            ),
            entries=(
                EtcEntry(renderer_type=RendererType.MAKO, path='local/ssh/sshd_config',
                         checkpoint=Checkpoint.INTERFACE_SYNC),
                EtcEntry(renderer_type=RendererType.MAKO, path='pam.d/sshd', local_path='pam.d/sshd_linux'),
                EtcEntry(renderer_type=RendererType.PY, path='local/ssh/config'),
                EtcEntry(renderer_type=RendererType.MAKO, path='login_banner', mode=0o600),
            ),
        ),
        'ntpd': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='chrony/chrony.conf'),
        )),
        'localtime': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='localtime_config'),
        )),
        'kmip': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='pykmip/pykmip.conf'),
        )),
        'truecommand': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='wireguard/ix-truecommand.conf'),
        )),
        'libvirt': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.PY, path='libvirt', checkpoint=None),
        )),
        'libvirt_guests': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='default/libvirt-guests', checkpoint=None),
        )),
        'subids': EtcGroup(entries=(
            EtcEntry(renderer_type=RendererType.MAKO, path='subuid', checkpoint=None),
            EtcEntry(renderer_type=RendererType.MAKO, path='subgid', checkpoint=None),
        )),
    }
    LOCKS: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(EtcService, self).__init__(*args, **kwargs)
        self.files_dir = os.path.realpath(
            os.path.join(os.path.dirname(__file__), '..', 'etc_files')
        )
        self._renderers = {
            RendererType.MAKO: MakoRenderer(self),
            RendererType.PY: PyRenderer(self),
        }

    async def gather_ctx(self, methods: list[CtxMethod]) -> dict:
        rv = {}
        for m in methods:
            key = f'{m.ctx_prefix}.{m.method}' if m.ctx_prefix else m.method
            rv[key] = await self.middleware.call(m.method, *m.args)

        return rv

    def get_perms_and_ownership(self, entry: EtcEntry) -> dict:
        uid = self.middleware.call_sync('user.get_builtin_user_id', entry.owner) if entry.owner else DEFAULT_ETC_XID
        gid = self.middleware.call_sync('group.get_builtin_group_id', entry.group) if entry.group else DEFAULT_ETC_XID

        return {'uid': uid, 'gid': gid, 'perms': entry.mode}

    def make_changes(self, full_path, entry: EtcEntry, rendered):
        def opener(path, flags):
            return os.open(path, os.O_CREAT | os.O_RDWR, mode=entry.mode)

        outfile_dirname = os.path.dirname(full_path)
        if outfile_dirname != '/etc':
            os.makedirs(outfile_dirname, exist_ok=True)

        payload = self.get_perms_and_ownership(entry)
        try:
            changes = write_if_changed(full_path, rendered, **payload)
        except Exception:
            changes = 0
            self.logger.warning('%s: failed to write changes to configuration file', full_path, exc_info=True)

        if (unexpected_changes := changes & ~FileChanges.CONTENTS):
            self.logger.error(
                '%s: unexpected changes [%s] were made to configuration file that may '
                'allow unauthorized user to alter service behavior', full_path,
                ', '.join(FileChanges.dump(unexpected_changes))
            )

        return changes

    async def generate(self, name, checkpoint=None):
        group = self.GROUPS.get(name)
        if group is None:
            raise ValueError('{0} group not found'.format(name))

        output = []
        async with self.LOCKS[name]:
            ctx = await self.gather_ctx(group.ctx) if group.ctx else None

            for entry in group.entries:
                renderer = self._renderers.get(entry.renderer_type)
                if renderer is None:
                    raise ValueError(f'Unknown type: {entry.renderer_type}')

                if checkpoint:
                    if entry.checkpoint != checkpoint:
                        continue

                path = os.path.join(self.files_dir, entry.local_path or entry.path)
                entry_path = entry.path
                if entry_path.startswith('local/'):
                    entry_path = entry_path[len('local/'):]
                outfile = f'/etc/{entry_path}'

                try:
                    rendered = await renderer.render(path, ctx)
                except FileShouldNotExist:
                    try:
                        await self.middleware.run_in_thread(os.unlink, outfile)
                        self.logger.debug(f'{entry.renderer_type}:{entry.path} file removed.')
                        output.append({
                            'path': outfile,
                            'status': 'REMOVED',
                            'changes': FileChanges.dump(FileChanges.CONTENTS)
                        })
                    except FileNotFoundError:
                        # Nothing to log
                        pass

                    continue
                except Exception:
                    self.logger.error(f'Failed to render {entry.renderer_type}:{entry.path}', exc_info=True)
                    continue

                if rendered is None:
                    # TODO: scripts that write config files internally should be refacorted
                    # to return bytes or str so that we can properly monitor for changes
                    continue

                changes = await self.middleware.run_in_thread(self.make_changes, outfile, entry, rendered)

                if not changes:
                    self.logger.trace('No new changes for %s', outfile)

                else:
                    output.append({
                        'path': outfile,
                        'status': 'CHANGED',
                        'changes': FileChanges.dump(changes)
                    })

        return output

    async def generate_checkpoint(self, checkpoint):
        try:
            checkpoint = Checkpoint(checkpoint)
        except ValueError:
            raise CallError(f'"{checkpoint}" not recognised')

        for name in self.GROUPS.keys():
            try:
                await self.generate(name, checkpoint)
            except Exception:
                self.logger.error(f'Failed to generate {name} group', exc_info=True)


async def __event_system_ready(middleware, event_type, args):
    middleware.create_task(middleware.call('etc.generate_checkpoint', 'post_init'))


async def pool_post_import(middleware, pool):
    if pool is None:
        await middleware.call('etc.generate_checkpoint', 'pool_import')


async def setup(middleware):
    middleware.event_subscribe('system.ready', __event_system_ready)
    # Generate `etc` files before executing other post-boot-time-pool-import actions.
    # There are no explicit requirements for that, we are just preserving execution order
    # when moving checkpoint generation to pool.post_import hook.
    middleware.register_hook('pool.post_import', pool_post_import, order=-1000)
