import subprocess
from logging import getLogger

from .ethtool import DeviceNotFound, OperationNotSupported, get_ethtool
from .utils import run


logger = getLogger(__name__)


class EthernetHardwareSettings:

    def __init__(self, interface):
        self._name = interface
        self._caps = self.__capabilities__()
        self._media = self.__mediainfo__()

    def __capabilities__(self):
        result = {'enabled': [], 'disabled': [], 'supported': []}
        return result

        # FIXME: unused and very inefficient with overall
        # design. Must be fixed properly in future. For now,
        # disable it.
        try:
            eth = get_ethtool()
            result = eth.get_features(self._name)
        except (OperationNotSupported, DeviceNotFound):
            pass
        except Exception:
            logger.error('Failed to get capabilities for %s', self._name, exc_info=True)
        return result

    def __set_features__(self, action, capabilities):
        # c.f. comment in self.__capabilities__()
        return

        features_to_change = []
        for cap in capabilities:
            if action == 'enable' and cap in self.disabled_capabilities:
                features_to_change.append(cap)
            elif action == 'disable' and cap in self.enabled_capabilities:
                features_to_change.append(cap)

        if not features_to_change:
            return

        cmd = ['ethtool', '-K', self._name]
        value = 'on' if action == 'enable' else 'off'
        for feature in features_to_change:
            if feature not in self.supported_capabilities:
                logger.error('Feature "%s" not found on interface "%s"', feature, self._name)
                continue
            cmd.extend([feature, value])

        if len(cmd) > 3:
            try:
                run(cmd)
            except subprocess.CalledProcessError as e:
                logger.error('Failed to set features on %s: %s', self._name, e.stderr)

    @property
    def enabled_capabilities(self):
        return self._caps['enabled']

    @enabled_capabilities.setter
    def enabled_capabilities(self, capabilities):
        # c.f. comment in self.__capabilities__()
        return
        self.__set_features__('enable', capabilities)

    @property
    def disabled_capabilities(self):
        return self._caps['disabled']

    @disabled_capabilities.setter
    def disabled_capabilities(self, capabilities):
        # c.f. comment in self.__capabilities__()
        return
        self.__set_features__('disable', capabilities)

    @property
    def supported_capabilities(self):
        return self._caps['supported']

    def __mediainfo__(self):
        result = {
            'media_type': '',
            'media_subtype': '',
            'active_media_type': '',
            'active_media_subtype': '',
            'supported_media': [],
        }
        try:
            eth = get_ethtool()
            link_modes = eth.get_link_modes(self._name)
            port = eth.get_link_info(self._name)['port']
            speed = link_modes['speed']
            autoneg = link_modes['autoneg']
            supported_modes = link_modes['supported_modes']
            mst = 'Unknown'
            if speed is not None and speed > 0:
                mst = f'{speed}Mb/s'
            mst = f'{mst} {port}'

            result['media_type'] = 'Ethernet'
            result['media_subtype'] = 'autoselect' if autoneg else mst
            result['active_media_type'] = 'Ethernet'
            result['active_media_subtype'] = mst
            result['supported_media'].extend(supported_modes)
        except (OperationNotSupported, DeviceNotFound):
            pass
        except Exception:
            logger.error('Failed to get media info for %s', self._name, exc_info=True)
        return result

    @property
    def media_type(self):
        return self._media['media_type']

    @property
    def media_subtype(self):
        return self._media['media_subtype']

    @property
    def active_media_type(self):
        return self._media['active_media_type']

    @property
    def active_media_subtype(self):
        return self._media['active_media_subtype']

    @property
    def supported_media(self):
        return self._media['supported_media']

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.close()
