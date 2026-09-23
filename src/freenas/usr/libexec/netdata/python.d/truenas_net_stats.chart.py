import errno
from contextlib import ExitStack

from bases.FrameworkServices.SimpleService import SimpleService
from truenas_pynetif.address import IFOperState, RTMGroup, get_link_stats, get_links, netlink_route
from truenas_pynetif.ethtool import NetlinkError, close_ethtool, get_ethtool
from truenas_pynetif.utils import INTERNAL_INTERFACES


class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.stack = None

    def check(self):
        return True

    def get_data(self):
        try:
            if self.stack is None:
                self.connect()
            elif self.links_changed():
                self.refresh_links()

            data = {}
            for index, stats in get_link_stats(self.sock).items():
                if index in self.links:
                    name, up, speed = self.links[index]
                    data[f"{name}.received"] = stats.rx_bytes
                    data[f"{name}.sent"] = stats.tx_bytes
                    data[f"{name}.up"] = up
                    data[f"{name}.speed"] = speed
            return data
        except Exception:
            # a failed request can leave the rest of its reply queued, so start over on new sockets
            self.disconnect()
            raise

    def connect(self):
        self.stack = ExitStack()
        # subscribe before get_links() so no link change can fall between the two
        self.events = self.stack.enter_context(netlink_route(groups=RTMGroup.LINK))
        self.events.setblocking(False)
        self.sock = self.stack.enter_context(netlink_route())
        self.refresh_links()

    def disconnect(self):
        self.stack.close()
        self.stack = None
        close_ethtool()

    def links_changed(self):
        changed = False
        try:
            while self.events.recv(65536):
                changed = True
        except BlockingIOError:
            pass
        except OSError as e:
            if e.errno != errno.ENOBUFS:
                raise
            changed = True
        return changed

    def refresh_links(self):
        self.links = {}
        for name, link in get_links(self.sock).items():
            if name.startswith(INTERNAL_INTERFACES):
                continue
            up = link.operstate == IFOperState.UP
            self.links[link.index] = (name, up, self.link_speed(name) if up else 0)
            if f"traffic.{name}" not in self.charts:
                self.add_charts(name)

    @staticmethod
    def link_speed(name):
        try:
            return get_ethtool().get_link_modes(name)["speed"] or 0
        except NetlinkError:
            return 0

    def add_charts(self, name):
        self.charts.add_chart(
            [f"traffic.{name}", None, "Traffic", "kilobits/s", name, "truenas_net_stats.traffic", "line"]
        )
        self.charts.add_chart([f"speed.{name}", None, "Speed", "Mbit/s", name, "truenas_net_stats.speed", "line"])
        self.charts.add_chart(
            [f"operstate.{name}", None, "Operational state", "state", name, "truenas_net_stats.operstate", "line"]
        )
        self.charts[f"traffic.{name}"].add_dimension([f"{name}.received", "received", "incremental", 8, 1000])
        self.charts[f"traffic.{name}"].add_dimension([f"{name}.sent", "sent", "incremental", 8, 1000])
        self.charts[f"speed.{name}"].add_dimension([f"{name}.speed", "speed", "absolute"])
        self.charts[f"operstate.{name}"].add_dimension([f"{name}.up", "up", "absolute"])
