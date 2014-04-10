=========
Jails
=========

Resources related to FreeBSD Jails.


Jails
--------

The Jails resource represents FreeBSD Jails.

List resource
+++++++++++++

.. http:get:: /api/v1.0/jails/jails/

   Returns a list of all jails.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/jails/jails/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
          "id": 1,
          "jail_alias_bridge_ipv4": null,
          "jail_alias_bridge_ipv6": null,
          "jail_alias_ipv4": null,
          "jail_alias_ipv6": null,
          "jail_autostart": True,
          "jail_bridge_ipv4": null,
          "jail_bridge_ipv4_netmask": "",
          "jail_bridge_ipv6": null,
          "jail_bridge_ipv6_prefix": "",
          "jail_defaultrouter_ipv4": null,
          "jail_defaultrouter_ipv6": null,
          "jail_flags": "allow.raw_sockets=true",
          "jail_host": "transmission_1",
          "jail_ipv4": "192.168.3.2",
          "jail_ipv4_netmask": "24",
          "jail_ipv6": null,
          "jail_ipv6_prefix": "",
          "jail_mac": "02:c3:79:00:08:0b",
          "jail_nat": false,
          "jail_status": "Running",
          "jail_type": "pluginjail",
          "jail_vnet": true
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/jails/jails/

   Creates a new jail and returns the new jail object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/jails/jails/ HTTP/1.1
      Content-Type: application/json

        {
          "jail_host": "test",
          "jail_type": "pluginjail"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
          "id": 1,
          "jail_alias_bridge_ipv4": null,
          "jail_alias_bridge_ipv6": null,
          "jail_alias_ipv4": null,
          "jail_alias_ipv6": null,
          "jail_autostart": true,
          "jail_bridge_ipv4": null,
          "jail_bridge_ipv4_netmask": "",
          "jail_bridge_ipv6": null,
          "jail_bridge_ipv6_prefix": "",
          "jail_defaultrouter_ipv4": null,
          "jail_defaultrouter_ipv6": null,
          "jail_flags": "allow.raw_sockets=true",
          "jail_host": "transmission_1",
          "jail_ipv4": "192.168.3.2",
          "jail_ipv4_netmask": "24",
          "jail_ipv6": null,
          "jail_ipv6_prefix": "",
          "jail_mac": "02:c3:79:00:08:0b",
          "jail_nat": false,
          "jail_status": "Running",
          "jail_type": "pluginjail",
          "jail_vnet": true
        }

   :json string jail_alias_bridge_ipv4: ipv4 bridge address
   :json string jail_alias_bridge_ipv6: ipv6 bridge address
   :json string jail_alias_ipv4: ipv4 address aliases
   :json string jail_alias_ipv6: ipv6 address aliases
   :json boolean jail_autostart: automatically start jail at boot
   :json string jail_bridge_ipv4: ipv4 bridge
   :json string jail_bridge_ipv4_netmask: ipv4 netmask
   :json string jail_bridge_ipv6: ipv6 bridge
   :json string jail_bridge_ipv6_prefix: ipv6 prefix
   :json string jail_defaultrouter_ipv4: ipv4 default route
   :json string jail_defaultrouter_ipv6: ipv6 default route
   :json string jail_flags: sysctl jail flags
   :json string jail_host: hostname of the jail
   :json string jail_ipv4: ipv4 address of the jail
   :json string jail_ipv4_netmask: ipv4 netmask (8, 16, 24, 32)
   :json string jail_ipv6: ipv6 address of the jail
   :json string jail_ipv6_prefix: ipv6 prefix
   :json string jail_mac: mac address for the jail interface
   :json boolean jail_nat: enable NAT for the jail
   :json string jail_status: current status of the jail
   :json string jail_type: type of the jail (pluginjail, standard, portjail, ...)
   :json boolean jail_vnet: enable VIMAGE for the jail
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Start jail
+++++++++++++++

.. http:post:: /api/v1.0/jails/jails/(int:id)/start/

   Starts a jail.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/jails/jails/1/start HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        Jail started.

   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/jails/jails/(int:id)/

   Delete jail `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/jails/jails/2/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
