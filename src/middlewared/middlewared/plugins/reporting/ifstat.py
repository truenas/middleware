from pyroute2.ethtool import Ethtool
from pyroute2.ethtool.ioctl import NotSupportedError, NoSuchDevice
from psutil import net_if_stats, net_io_counters


class IfStats(object):

    def __init__(self, interval, prev_data, ignore_ifaces):
        self.interval = interval
        self.prev_data = prev_data
        self.ignore = ignore_ifaces
        self.eth = Ethtool()

    def __enter__(self):
        return self.read()

    def __exit__(self, _type, _value, _tb):
        self.eth.close()
        self.eth = None

    def get_link_state(self, isup):
        return 'LINK_STATE_UP' if isup else 'LINK_STATE_DOWN'

    def get_link_speed(self, iface):
        try:
            speed = self.eth.get_link_mode(iface, with_netlink=False).speed
        except (NotSupportedError, NoSuchDevice, Exception):
            # NotSupportedError:
            # ----running as a VM randomly reports NotSupportedError

            # NoSuchDevice:
            # ----udevd renames interfaces from "old" names (eth0) to new (enp5s0)
            # ----[2.283069] r8169 0000:05:00.0 enp5s0: renamed from eth0

            # ----also saw a driver problem with 2.5Gb Realteck card (go figure)
            # ----[4205.447000] RTL8226 2.5Gbps PHY r8169-500:00: attached PHY driver

            # Exception:
            # ----catch anything else since this is in reporting plugin
            speed = None

        return speed

    def read(self):
        ifs = net_if_stats()
        ioc = net_io_counters(pernic=True)
        curr_data = dict()
        new_data = dict()
        for nic, iodata in filter(lambda x: x[0] not in self.ignore and x[0] in ifs, ioc.items()):
            curr_data[nic] = dict()
            new_data[nic] = dict()

            link_state = self.get_link_state(ifs[nic].isup)
            curr_data[nic]['link_state'] = link_state
            new_data[nic]['link_state'] = link_state

            speed = self.get_link_speed(nic)
            curr_data[nic]['speed'] = speed
            new_data[nic]['speed'] = speed

            rx_bytes = iodata.bytes_recv
            tx_bytes = iodata.bytes_sent
            curr_data[nic]['received_bytes'] = rx_bytes
            curr_data[nic]['sent_bytes'] = tx_bytes

            # diff between curr_data and self.prev_data
            if link_state == 'LINK_STATE_UP':
                new_data[nic]['received_bytes'] = rx_bytes - self.prev_data.get(nic, {}).get('received_bytes', 0)
                new_data[nic]['sent_bytes'] = tx_bytes - self.prev_data.get(nic, {}).get('sent_bytes', 0)
                new_data[nic]['received_bytes_rate'] = new_data[nic]['received_bytes'] / self.interval
                new_data[nic]['sent_bytes_rate'] = new_data[nic]['sent_bytes'] / self.interval
            else:
                # nic could have been up and is now down so no reason to do calculation
                # just fill with zeros
                new_data[nic]['received_bytes'] = 0
                new_data[nic]['sent_bytes'] = 0
                new_data[nic]['received_bytes_rate'] = 0.0
                new_data[nic]['sent_bytes_rate'] = 0.0


        return curr_data, new_data
