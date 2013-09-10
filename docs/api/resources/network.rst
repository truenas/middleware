=========
Network
=========

Resources related to network.

Interfaces
----------

The Interfaces resource represents network interfaces configuration.

List resource
+++++++++++++

.. http:get:: /api/v1.0/network/interfaces/

   Returns a list of all interfaces.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/network/interfaces/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "int_v6netmaskbit": "",
                "int_ipv4address": "192.168.3.20",
                "int_name": "ext",
                "int_ipv6address": "",
                "int_dhcp": false,
                "int_options": "",
                "int_v4netmaskbit": "24",
                "ipv6_addresses": [],
                "int_aliases": [],
                "int_ipv6auto": true,
                "ipv4_addresses": [
                        "192.168.3.20/24",
                ],
                "int_interface": "em0",
                "id": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/network/interfaces/

   Creates a new cronjob and returns the new cronjob object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/network/interfaces/ HTTP/1.1
      Content-Type: application/json

        {
                "int_ipv4address": "192.168.3.20",
                "int_name": "ext",
                "int_v4netmaskbit": "24",
                "int_interface": "em0",
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "int_v6netmaskbit": "",
                "int_ipv4address": "192.168.3.20",
                "int_name": "ext",
                "int_ipv6address": "",
                "int_dhcp": false,
                "int_options": "",
                "int_v4netmaskbit": "24",
                "ipv6_addresses": [],
                "int_aliases": [],
                "int_ipv6auto": true,
                "ipv4_addresses": [
                        "192.168.3.20/24",
                ],
                "int_interface": "em0",
                "id": 1
        }

   :json string int_name: user name for the interface
   :json string int_interface: name of the physical interface
   :json string int_ipv4address: main IPv4 address
   :json string int_v4netmaskbit: number of bits for netmask (1..32)
   :json string int_ipv6address: main IPv6 address
   :json string int_v6netmaskbit: number of bits for netmask [0, 48, 60, 64, 80, 96]
   :json boolean int_dhcp: enable DHCP
   :json boolean int_ipv6auto: enable auto IPv6
   :json string int_options: extra options to ifconfig(8)
   :json list(string) int_aliases: list of IP addresses as aliases
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/network/interfaces/(int:id)/

   Update cronjob `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/network/interfaces/1/ HTTP/1.1
      Content-Type: application/json

        {
                "int_ipv4address": "192.168.3.21"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "int_v6netmaskbit": "",
                "int_ipv4address": "192.168.3.21",
                "int_name": "ext",
                "int_ipv6address": "",
                "int_dhcp": false,
                "int_options": "",
                "int_v4netmaskbit": "24",
                "ipv6_addresses": [],
                "int_aliases": [],
                "int_ipv6auto": true,
                "ipv4_addresses": [
                        "192.168.3.20/24",
                ],
                "int_interface": "em0",
                "id": 1
        }

   :json string int_name: user name for the interface
   :json string int_interface: name of the physical interface
   :json string int_ipv4address: main IPv4 address
   :json string int_v4netmaskbit: number of bits for netmask (1..32)
   :json string int_ipv6address: main IPv6 address
   :json string int_v6netmaskbit: number of bits for netmask [0, 48, 60, 64, 80, 96]
   :json boolean int_dhcp: enable DHCP
   :json boolean int_ipv6auto: enable auto IPv6
   :json string int_options: extra options to ifconfig(8)
   :json list(string) int_aliases: list of IP addresses as aliases
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/network/interfaces/(int:id)/

   Delete cronjob `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/network/interfaces/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
