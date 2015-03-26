=========
Jails
=========

Resources related to FreeBSD Jails.


Configuration
-------------

The Configuration resource exposes settings related to jails.

List resource
+++++++++++++

.. http:get:: /api/v1.0/jails/configuration/

   Returns the configuration dictionary.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/jails/configuration/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
          "id": 1,
          "jc_collectionurl": "http://cdn.freenas.org/latest/RELEASE/x64/jails",
          "jc_ipv4_network": "192.168.3.0/24",
          "jc_ipv4_network_end": "192.168.3.254",
          "jc_ipv4_network_start": "192.168.3.34",
          "jc_ipv6_network": "",
          "jc_ipv6_network_end": "",
          "jc_ipv6_network_start": "",
          "jc_path": "/mnt/tank/jails"
        }

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error

   
Update resource
+++++++++++++

.. http:put:: /api/v1.0/jails/configuration/

   Update the configuration dictionary.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/jails/configuration/ HTTP/1.1
      Content-Type: application/json

        {
          "jc_ipv4_network_start": "192.168.3.50"
        }
        
   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
          "id": 1,
          "jc_collectionurl": "http://cdn.freenas.org/latest/RELEASE/x64/jails",
          "jc_ipv4_network": "192.168.3.0/24",
          "jc_ipv4_network_end": "192.168.3.254",
          "jc_ipv4_network_start": "192.168.3.50",
          "jc_ipv6_network": "",
          "jc_ipv6_network_end": "",
          "jc_ipv6_network_start": "",
          "jc_path": "/mnt/tank/jails"
        }

   :json string jc_collectionurl: URL for the jail index
   :json string jc_ipv4_network: IPv4 network range for jails and plugins
   :json string jc_ipv4_network_start: IPv4 Network Start Address
   :json string jc_ipv4_network_end: IPv4 Network End Address
   :json string jc_ipv6_network: IPv6 network range for jails and plugins
   :json string jc_ipv6_network_start: IPv6 network start address for jails and plugins
   :json string jc_ipv6_network_end: IPv6 network end address for jails and plugins
   :json string jc_path: dataset the jails will reside within
   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


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

      POST /api/v1.0/jails/jails/1/start/ HTTP/1.1
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


Stop jail
+++++++++++++++

.. http:post:: /api/v1.0/jails/jails/(int:id)/stop/

   Stops a jail.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/jails/jails/1/stop/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        Jail stopped.

   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 202: no error


Restart jail
+++++++++++++++

.. http:post:: /api/v1.0/jails/jails/(int:id)/restart/

   Starts a jail.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/jails/jails/1/restart/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: application/json

        Jail restarted.

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


MountPoints
-----------

The MountPoints resource represents filesystem mounts (nullfs) to jails.

List resource
+++++++++++++

.. http:get:: /api/v1.0/jails/mountpoints/

   Returns a list of all mountpoints.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/jails/mountpoints/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
          "id": 1,
          "destination": "/mnt",
          "jail": "transmission_1",
          "mounted": true,
          "readonly": false,
          "source": "/mnt/tank/test"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/jails/mountpoints/

   Creates a new mountpoint and returns the object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/jails/mountpoints/ HTTP/1.1
      Content-Type: application/json

        {
          "destination": "/mnt",
          "jail": "transmission_1",
          "mounted": true,
          "readonly": false,
          "source": "/mnt/tank/test"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
          "id": 1,
          "destination": "/mnt",
          "jail": "transmission_1",
          "mounted": true,
          "readonly": false,
          "source": "/mnt/tank/test"
        }

   :json string jail: name of the jail
   :json string source: path source in the host
   :json string destination: path destination within the jail root
   :json string mounted: where the path is/should be mounted
   :json string readonly: mount as read-only
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error

Update resource
+++++++++++++++

.. http:put:: /api/v1.0/jails/mountpoints/(int:id)/

   Updates a mountpoint object.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/jails/mountpoints/1/ HTTP/1.1
      Content-Type: application/json

        {
          "source": "/mnt/tank/test2"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
          "id": 1,
          "destination": "/mnt",
          "jail": "transmission_1",
          "mounted": true,
          "readonly": false,
          "source": "/mnt/tank/test2"
        }

   :json string jail: name of the jail
   :json string source: path source in the host
   :json string destination: path destination within the jail root
   :json string mounted: where the path is/should be mounted
   :json string readonly: mount as read-only
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/jails/mountpoints/(int:id)/

   Delete mountpoint `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/jails/mountpoints/1/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error


Templates
---------

The Templates resource represents templates to be used for FreeBSD Jails.

List resource
+++++++++++++

.. http:get:: /api/v1.0/jails/templates/

   Returns a list of all templates.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/jails/templates/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

      [
        {
          "id": 1,
          "jt_arch": "x64",
          "jt_instances": 0,
          "jt_name": "pluginjail",
          "jt_os": "FreeBSD",
          "jt_url": "http://download.freenas.org/jails/9.2/x64/freenas-pluginjail-9.2-RELEASE.tgz"
        },
        {
          "id": 2,
          "jt_arch": "x64",
          "jt_instances": 0,
          "jt_name": "portjail",
          "jt_os": "FreeBSD",
          "jt_url": "http://download.freenas.org/jails/9.2/x64/freenas-portjail-9.2-RELEASE.tgz"
        },
        {
          "id": 3,
          "jt_arch": "x64",
          "jt_instances": 0,
          "jt_name": "standard",
          "jt_os": "FreeBSD",
          "jt_url": "http://download.freenas.org/jails/9.2/x64/freenas-standard-9.2-RELEASE.tgz"
        },
        {
          "id": 4,
          "jt_arch": "x86",
          "jt_instances": 0,
          "jt_name": "debian-7.1.0",
          "jt_os": "Linux",
          "jt_url": "http://download.freenas.org/jails/9.2/x64/linux-debian-7.1.0.tgz"
        },
        {
          "id": 5,
          "jt_arch": "x86",
          "jt_instances": 0,
          "jt_name": "gentoo-20130820",
          "jt_os": "Linux",
          "jt_url": "http://download.freenas.org/jails/9.2/x64/linux-gentoo-20130820.tgz"
        },
        {
          "id": 6,
          "jt_arch": "x86",
          "jt_instances": 0,
          "jt_name": "ubuntu-13.04",
          "jt_os": "Linux",
          "jt_url": "http://download.freenas.org/jails/9.2/x64/linux-ubuntu-13.04.tgz"
        },
        {
          "id": 8,
          "jt_arch": "x86",
          "jt_instances": 0,
          "jt_name": "suse-12.3",
          "jt_os": "Linux",
          "jt_url": "http://download.freenas.org/jails/9.2/x64/linux-suse-12.3.tgz"
        },
        {
          "id": 9,
          "jt_arch": "x86",
          "jt_instances": 0,
          "jt_name": "centos-6.4",
          "jt_os": "Linux",
          "jt_url": "http://download.freenas.org/jails/9.2/x64/linux-centos-6.4.tgz"
        },
        {
          "id": 10,
          "jt_arch": "x86",
          "jt_instances": 0,
          "jt_name": "pluginjail-x86",
          "jt_os": "FreeBSD",
          "jt_url": "http://download.freenas.org/jails/9.2/x86/freenas-pluginjail-9.2-RELEASE.tgz"
        },
        {
          "id": 11,
          "jt_arch": "x86",
          "jt_instances": 0,
          "jt_name": "portjail-x86",
          "jt_os": "FreeBSD",
          "jt_url": "http://download.freenas.org/jails/9.2/x86/freenas-portjail-9.2-RELEASE.tgz"
        },
        {
          "id": 12,
          "jt_arch": "x86",
          "jt_instances": 0,
          "jt_name": "standard-x86",
          "jt_os": "FreeBSD",
          "jt_url": "http://download.freenas.org/jails/9.2/x86/freenas-standard-9.2-RELEASE.tgz"
        },
        {
          "id": 13,
          "jt_arch": "x64",
          "jt_instances": 0,
          "jt_name": "VirtualBox-4.3.12",
          "jt_os": "FreeBSD",
          "jt_url": "http://download.freenas.org/jails/9.2/x64/freenas-virtualbox-4.3.12.tgz"
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/jails/templates/

   Creates a new template and returns the new object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/jails/templates/ HTTP/1.1
      Content-Type: application/json

        {
          "jt_name": "My Template",
          "jt_os": "FreeBSD",
          "jt_arch": "x64",
          "jt_url": "http://example.com/jails/mytemplate_x64.tgz"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: application/json

        {
          "id": 14,
          "jt_name": "My Template",
          "jt_os": "FreeBSD",
          "jt_arch": "x64",
          "jt_instances": 0,
          "jt_url": "http://example.com/jails/mytemplate_x64.tgz"
        }

   :json string jt_name: name of the template
   :json string jt_os: type of the OS (FreeBSD/Linux)
   :json string jt_arch: jail architecture (x64/x86)
   :json string jt_url: url of the template
   :json string jt_instances: read-only, number of instances using this template
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Update resource
+++++++++++++++

.. http:put:: /api/v1.0/jails/templates/(int:id)/

   Updates a template object.

   **Example request**:

   .. sourcecode:: http

      PUT /api/v1.0/jails/templates/14/ HTTP/1.1
      Content-Type: application/json

        {
          "jt_url": "http://example.com/jails/mytemplate_2_x64.tgz"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: application/json

        {
          "id": 14,
          "jt_name": "My Template",
          "jt_os": "FreeBSD",
          "jt_arch": "x64",
          "jt_instances": 0,
          "jt_url": "http://example.com/jails/mytemplate_2_x64.tgz"
        }

   :json string jt_name: name of the template
   :json string jt_os: type of the OS (FreeBSD/Linux)
   :json string jt_arch: jail architecture (x64/x86)
   :json string jt_url: url of the template
   :json string jt_instances: read-only, number of instances using this template
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 200: no error


Delete resource
+++++++++++++++

.. http:delete:: /api/v1.0/jails/templates/(int:id)/

   Delete template `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/jails/templates/14/ HTTP/1.1
      Content-Type: application/json

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: application/json

   :statuscode 204: no error
