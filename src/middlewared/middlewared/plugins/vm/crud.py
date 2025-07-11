import errno
import re
import uuid

from middlewared.service import CallError, private
from .utils import ACTIVE_STATES, get_default_status

RE_NAME = re.compile(r'^[a-zA-Z_0-9]+$')


class VMCRUDMixin:
    @private
    def extend_context(self, rows, extra):
        status = {}
        shutting_down = self.middleware.call_sync('system.state') == 'SHUTTING_DOWN'
        kvm_supported = self._is_kvm_supported()
        if shutting_down is False and rows and kvm_supported:
            self._safely_check_setup_connection(5)

        libvirt_running = shutting_down is False and self._is_connection_alive()
        for row in rows:
            status[row['id']] = self.status_impl(row) if libvirt_running else get_default_status()

        return {
            'status': status,
        }

    @private
    async def extend(self, vm, context):
        vm['status'] = context['status'][vm['id']]
        return vm

    @private
    def status_impl(self, vm):
        if self._has_domain(vm['name']):
            try:
                # Whatever happens, query shouldn't fail
                return self._status(vm['name'])
            except Exception:
                self.logger.debug('Failed to retrieve VM status for %r', vm['name'], exc_info=True)

        return get_default_status()

    @private
    async def base_common_validation(self, plugin, verrors, schema_name, data, old=None):
        if not data.get('uuid'):
            data['uuid'] = str(uuid.uuid4())

        if 'name' in data:
            filters = {
                'container': [('name', '=', data['name'])],
                'vm': [('name', '=', data['name'])],
            }
            if old:
                filters[plugin].append(('id', '!=', old['id']))

            if await self.middleware.call('container.query', filters['container']):
                verrors.add(
                    f'{schema_name}.name',
                    'A container with this name already exists.', errno.EEXIST
                )
            elif await self.middleware.call('vm.query', filters['vm']):
                verrors.add(
                    f'{schema_name}.name',
                    'A VM with this name already exists.', errno.EEXIST
                )
            elif not RE_NAME.search(data['name']):
                verrors.add(
                    f'{schema_name}.name',
                    'Only alphanumeric characters are allowed.'
                )

    @private
    async def pre_update(self, old, new, type_):
        if new['name'] != old['name']:
            await self.middleware.run_in_thread(self._check_setup_connection)
            if old['status']['state'] in ACTIVE_STATES:
                raise CallError(f'{type_} name can only be changed when {type_} is inactive')

            if old['name'] not in self.vms:
                raise CallError(f'Unable to locate domain for {old["name"]}')
