try:
    import sysctl
except ImportError:
    sysctl = None

from lxml import etree

from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list, osc


class MultipathService(CRUDService):

    class Config:
        cli_namespace = "storage.multipath"

    @filterable
    def query(self, filters, options):
        """
        Get multipaths and their consumers.

        .. examples(websocket)::

          Get all multipaths

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "multipath.query",
                "params": []
            }

            returns

            :::javascript
            [
              {
                "type": "root",
                "name": "multipath/disk5",
                "status": "OPTIMAL",
                "children": [
                  {
                    "type": "consumer",
                    "name": "da1",
                    "status": "PASSIVE",
                    "lun_id": "5000cca05c9e1400"
                  },
                  {
                    "type": "consumer",
                    "name": "da23",
                    "status": "ACTIVE",
                    "lun_id": "5000cca05c9e1400"
                  }
                ]
              }
            ]
        """

        if osc.IS_LINUX:
            return []

        multipaths = self.__get_multipaths()

        items = []
        for mp in multipaths:
            children = []
            for cn in mp.consumers:
                children.append({
                    "type": "consumer",
                    "name": cn.devname,
                    "status": cn.status,
                    "lun_id": cn.lunid,
                })

            data = {
                "type": "root",
                "name": mp.devname,
                "status": mp.status,
                "children": children,
            }
            items.append(data)

        return filter_list(items, filters=filters or [], options=options or {})

    def __get_multipaths(self):
        doc = etree.fromstring(sysctl.filter("kern.geom.confxml")[0].value)
        return [
            Multipath(doc=doc, xmlnode=geom)
            for geom in doc.xpath("//class[name = 'MULTIPATH']/geom")
        ]


class Multipath(object):
    """
    Class representing a GEOM_MULTIPATH
    """

    @property
    def status(self):
        return getattr(self, "_status", "Unknown")

    @status.setter
    def status(self, value):
        self._status = value

    @property
    def devices(self):
        devs = []
        for consumer in self.consumers:
            devs.append(consumer.devname)
        return devs

    def __init__(self, doc, xmlnode):
        self.name = xmlnode.xpath("./name")[0].text
        self.devname = f"multipath/{self.name}"
        self._status = xmlnode.xpath("./config/State")[0].text
        self.consumers = []
        for consumer in xmlnode.xpath("./consumer"):
            status = consumer.xpath("./config/State")[0].text
            provref = consumer.xpath("./provider/@ref")[0]
            prov = doc.xpath(f"//provider[@id = '{provref}']")[0]
            self.consumers.append(Consumer(status, prov))

        self.__xml = xmlnode
        self.__doc = doc

    def __repr__(self):
        return f"<Multipath:{self.name} [{','.join(self.devices)}]>"


class Consumer(object):

    def __init__(self, status, xmlnode):
        self.status = status
        self.devname = xmlnode.xpath("./name")[0].text
        try:
            self.lunid = xmlnode.xpath("./config/lunid")[0].text
        except Exception:
            self.lunid = ""
        self.__xml = xmlnode
