from middlewared.service import CRUDService, filterable


class MultipathService(CRUDService):

    class Config:
        datastore_primary_key = 'name'
        datastore_primary_key_type = 'string'
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
        # TODO: multipath not implemented on SCALE, yet
        return []
