from xml.etree import ElementTree as ET

import sysctl
from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list


class MultipathService(CRUDService):

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
        return filter_list(self.__get_multipaths(), filters=filters or [], options=options or {})

    def __get_multipaths(self):
        doc = ET.fromstring(sysctl.filter("kern.geom.confxml")[0].value)
        result = []
        for g in doc.iterfind(".//class[name = 'MULTIPATH']/geom"):
            # get gmultipath consumer information
            children = []
            for i in g.findall('./consumer'):
                consumer_status = i.find('./config/State').text
                provref = i.find('./provider').attrib['ref']
                prov = doc.findall(f'.//provider[@id="{provref}"]')[0]
                da_name = prov.find('./name').text
                try:
                    lun_id = prov.find('./config/lunid').text
                except Exception:
                    lun_id = ''

                children.append({
                    'type': 'consumer',
                    'name': da_name,
                    'status': consumer_status,
                    'lun_id': lun_id,
                })

            result.append({
                'type': 'root',
                'name': 'multipath/' + g.find("./name").text,
                'status': g.find("./config/State").text,
                'children': children,
            }),
        else:
            doc = None
            return result
