=========
Network
=========

Resources related to network.


Global Configuration
--------------------

The GlobalConfiguration resource represents network general settings like
default gateway, nameservers, hostname, etc.

List resource
+++++++++++++

.. http:get:: /api/v1.0/network/globalconfiguration/

   Returns the global configuration dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/network/globalconfiguration/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
                "gc_domain": "local",
                "gc_ipv4gateway": "192.168.3.1",
                "gc_hostname": "freenas",
                "gc_netwait_enabled": false,
                "gc_hosts": "",
                "gc_ipv6gateway": "",
                "gc_netwait_ip": "",
                "gc_nameserver1": "192.168.3.1",
                "gc_nameserver3": "",
                "gc_nameserver2": "",
                "id": 1
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/network/globalconfiguration/

   Update global configuration `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/network/globalconfiguration/ HTTP/1.1
      Content-Type: application/json

        {
                "gc_hosts": "192.168.3.56 myownhost"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "gc_domain": "local",
                "gc_ipv4gateway": "192.168.3.1",
                "gc_hostname": "freenas",
                "gc_netwait_enabled": false,
                "gc_hosts": "192.168.3.56 myownhost",
                "gc_ipv6gateway": "",
                "gc_netwait_ip": "",
                "gc_nameserver1": "192.168.3.1",
                "gc_nameserver3": "",
                "gc_nameserver2": "",
                "id": 1
        }

   :json string gc_domain: domain
   :json string gc_hostname: hostname
   :json string gc_ipv4gateway: ipv4 address of the gateway
   :json string gc_ipv6gateway: ipv6 address of the gateway
   :json string gc_nameserver1: nameserver address #1
   :json string gc_nameserver2: nameserver address #2
   :json string gc_nameserver3: nameserver address #3
   :json boolean gc_netwait_enabled: enable netwait feature
   :json string gc_netwait_ip: list of IPs to wait before proceed the boot
   :json string gc_hosts: entries to append to /etc/hosts
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Interface
----------

The Interface resource represents network interfaces configuration.

List resource
+++++++++++++

.. http:get:: /api/v1.0/network/interface/

   Returns a list of all interfaces.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/network/interface/ HTTP/1.1
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

.. http:post:: /api/v1.0/network/interface/

   Creates a new Interface and returns the new Interface object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/network/interface/ HTTP/1.1
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

.. http:put:: /api/v1.0/network/interface/(int:id)/

   Update Interface `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/network/interface/1/ HTTP/1.1
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

.. http:delete:: /api/v1.0/network/interface/(int:id)/

   Delete cronjob `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/network/interface/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


VLAN
----------

The VLAN resource represents network vlan configuration.

List resource
+++++++++++++

.. http:get:: /api/v1.0/network/vlan/

   Returns a list of all VLANs.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/network/vlan/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "vlan_description": "",
                "vlan_pint": "em1",
                "vlan_tag": 0,
                "vlan_vint": "vlan0",
                "id": 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/network/vlan/

   Creates a new VLAN and returns the new VLAN object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/network/vlan/ HTTP/1.1
      Content-Type: application/json

        {
                "vlan_vint": "vlan0",
                "vlan_pint": "em1",
                "vlan_tag": 0,
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "vlan_description": "",
                "vlan_pint": "em1",
                "vlan_tag": 0,
                "vlan_vint": "vlan0",
                "id": 1
        }

   :json string vlan_pint: physical interface
   :json string vlan_vint: virtual interface name, vlanX
   :json string vlan_description: user description
   :json integer vlan_tag: vlan tag number
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/network/vlan/(int:id)/

   Update VLAN `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/network/vlan/1/ HTTP/1.1
      Content-Type: application/json

        {
                "vlan_tag": 1
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "vlan_description": "",
                "vlan_pint": "em1",
                "vlan_tag": 1,
                "vlan_vint": "vlan0",
                "id": 1
        }

   :json string vlan_pint: physical interface
   :json string vlan_vint: virtual interface name, vlanX
   :json string vlan_description: user description
   :json integer vlan_tag: vlan tag number
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/network/vlan/(int:id)/

   Delete VLAN `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/network/vlan/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


LAGG
----------

The LAGG resource represents network LAGG (Link Aggregation) configuration.

List resource
+++++++++++++

.. http:get:: /api/v1.0/network/lagg/

   Returns a list of all LAGGs.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/network/lagg/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
                "lagg_interface": "lagg0",
                "id": 1,
                "lagg_protocol": "roundrobin"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/network/lagg/

   Creates a new LAGG and returns the new LAGG object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/network/lagg/ HTTP/1.1
      Content-Type: application/json

        {
                "lagg_interfaces": ["em1"],
                "lagg_protocol": "roundrobin"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "lagg_interface": "lagg0",
                "id": 1,
                "lagg_protocol": "roundrobin"
        }

   :json list(string) lagg_interfaces: list of physical interface names
   :json string lagg_protocol: failover, fec, lacp, loadbalance, roundrobin, none
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/network/lagg/(int:id)/

   Delete LAGG `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/network/lagg/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Static Route
------------

The StaticRoute resource represents network routing tables route(8).

List resource
+++++++++++++

.. http:get:: /api/v1.0/network/staticroute/

   Returns a list of all static routes.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/network/staticroute/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/network/staticroute/

   Creates a new static route and returns the new static route object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/network/staticroute/ HTTP/1.1
      Content-Type: application/json

        {
                "sr_destination": "192.168.1.0/24",
                "sr_gateway": "192.168.3.1",
                "sr_description": "test route"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
                "sr_description": "test route",
                "sr_destination": "192.168.1.0/24",
                "id": 1,
                "sr_gateway": "192.168.3.1"
        }

   :json string sr_gateway: address of gateway
   :json string sr_destination: network cidr
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/network/staticroute/(int:id)/

   Update static route `id`.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/network/staticroute/1/ HTTP/1.1
      Content-Type: application/json

        {
                "sr_destination": "192.168.1.0/16"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        {
                "sr_description": "test route",
                "sr_destination": "192.168.1.0/16",
                "id": 1,
                "sr_gateway": "192.168.3.1"
        }

   :json string sr_gateway: address of gateway
   :json string sr_destination: network cidr
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/network/staticroute/(int:id)/

   Delete static route `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/network/staticroute/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
