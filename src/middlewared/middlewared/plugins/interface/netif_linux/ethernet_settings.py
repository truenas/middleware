from logging import getLogger
from pyroute2.ethtool import Ethtool
from pyroute2.ethtool.ioctl import NotSupportedError, NoSuchDevice


logger = getLogger(__name__)


class EthernetHardwareSettings:

    def __init__(self, interface):
        self._name = interface
        self._eth = Ethtool()
        self._caps = self.__capabilities__()
        self._media = self.__mediainfo__()

    def __capabilities__(self):
        result = {'enabled': [], 'disabled': [], 'supported': []}
        try:
            for i in self._eth.get_features(self._name):
                for name, feature in i.items():
                    if not name.strip() or not feature.available:
                        # testing shows that there are features
                        # without a name so make sure we ignore
                        # those as well as ignore the feature if
                        # it's not "available" to be changed
                        continue

                    if feature.enable:
                        result['enabled'].append(name)
                    else:
                        result['disabled'].append(name)
                    result['supported'].append(name)
        except Exception:
            logger.error('Failed to get capabilities for %s', self._name, exc_info=True)

        return result

    def __set_features__(self, action, capabilities):
        features = []
        for cap in capabilities:
            if action == 'enable' and cap in self.disabled_capabilities:
                # means the feature(s) being requested to be enabled is currently disabled
                features.append(cap)
            elif action == 'disable' and cap in self.enabled_capabilities:
                # means the feature(s) being requested to be disabled is currently enabled
                features.append(cap)

        if features:
            changed_features = self._eth.get_features(self._name)
            set_features = False
            for feature in features:
                try:
                    changed_features.features[feature].enable = True if action == 'enable' else False
                    set_features = True
                except KeyError:
                    logger.error('Feature "%s" not found on interface "%s"', feature, self._name)
                    continue

            if set_features:
                # actually send the request to the kernel to enable/disable the feature(s)
                self._eth.set_features(self._name, changed_features)

    @property
    def enabled_capabilities(self):
        return self._caps['enabled']

    @enabled_capabilities.setter
    def enabled_capabilities(self, capabilities):
        self.__set_features__('enable', capabilities)

    @property
    def disabled_capabilities(self):
        return self._caps['disabled']

    @disabled_capabilities.setter
    def disabled_capabilities(self, capabilities):
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

        # We use the undocumented `with_netlink=False` kwargs because
        # it was noticed that we were getting log spam on machines in
        # the lab.
        # Log message looks like:
        # "pyroute2.ethtool.ethtool.from_netlink():224 - Bit name is not the same as the target: FEC_NONE <> None"
        # This looks like a bug upstream but the keyword arg works around
        # the problem.
        try:
            attrs = self._eth.get_link_mode(self._name, with_netlink=False)
            mst = 'Unknown'
            if attrs.speed is not None:
                # looks like 1000Mb/s, 10000Mb/s, etc
                mst = f'{attrs.speed}Mb/s'

            # looks like ("Unknown Twisted Pair" OR "1000Mb/s Twisted Pair" etc
            mst = f'{mst} {self._eth.get_link_info(self._name, with_netlink=False).port}'

            # fill out the results
            result['media_type'] = 'Ethernet'
            result['media_subtype'] = 'autoselect' if attrs.autoneg else mst
            result['active_media_type'] = 'Ethernet'
            result['active_media_subtype'] = mst  # just matches media_subtype...gross
            result['supported_media'].extend(attrs.supported_modes)
        except (NotSupportedError, NoSuchDevice):
            # NotSupportedError:
            # ----saw this on a VM running inside xen where the
            # ----nic driver being used doesnt report any type
            # ----of media info (ethtool binary didnt report anything either)
            # ----so ignore these errors

            # NoSuchDevice:
            # ----udevd will rename interfaces from "old" names (eth0) to new names (enp5s0)
            # ----[2.283069] r8169 0000:05:00.0 enp5s0: renamed from eth0 (this is from dmesg)

            # ----For whatever, reason, ethtool will barf and say "No Such Device" even though
            # ----it clearly exists. By the time this method is called, the device exists but
            # ----we're failing because of a driver problem and/or because the device has been
            # ----renamed. Instead of spamming logs, just pass and return empty information

            # ----The situation I saw on real hardware is a Realtek card using the 2.5Gbps driver
            # ----[4205.447000] RTL8226 2.5Gbps PHY r8169-500:00: attached PHY driver
            # ----[RTL8226 2.5Gbps PHY] (mii_bus:phy_addr=r8169-500:00, irq=IGNORE)
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
        self._eth.close()

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.close()
