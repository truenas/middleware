from xml.etree import ElementTree as ET

from middlewared.service import Service
from middlewared.utils import filter_list, run
from .global_base import GlobalActionsBase


class ISCSIGlobalService(Service, GlobalActionsBase):

    class Config:
        datastore_extend = 'iscsi.global.config_extend'
        datastore_prefix = 'iscsi_'
        service = 'iscsitarget'
        service_model = 'iscsitargetglobalconfiguration'
        namespace = 'iscsi.global'

    async def sessions(self, filters, options):
        """
        Get a list of currently running iSCSI sessions. This includes initiator and target names
        and the unique connection IDs.
        """
        async def transform(tag, text):
            if tag in (
                'target_portal_group_tag', 'max_data_segment_length', 'max_burst_length',
                'first_burst_length',
            ) and text.isdigit():
                return int(text)
            if tag in ('immediate_data', 'iser'):
                return bool(int(text))
            if tag in ('header_digest', 'data_digest', 'offload') and text == 'None':
                return None
            return text

        sessions = []
        xml = (await run(
            ['ctladm', 'islist', '-x'],
            check=False,
            encoding='utf8'
        )).stdout
        for connection in ET.fromstring(xml).findall('.//connection'):
            sessions.append({
                i.tag: await transform(i.tag, i.text) for i in connection
            })
        return filter_list(sessions, filters, options)

    async def terminate_luns_for_pool(self, pool_name):
        xml = (await run(
            ['ctladm', 'devlist', '-b', 'block', '-x'],
            check=False,
            encoding='utf8'
        )).stdout
        for lun in ET.fromstring(xml).findall('.//lun'):
            lun_id = lun.attrib['id']

            path = lun.find('.//file').text
            if path is None:
                continue

            if path.startswith(f'/dev/zvol/{pool_name}/'):
                self.logger.info('Terminating LUN %s (%s)', lun_id, path)
                await run(['ctladm', 'remove', '-b', 'block', '-l', lun_id], check=False)
