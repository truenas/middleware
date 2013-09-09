=========
Account
=========

Resources related to accounts.

bsdUsers
----------

The bsdUsers resource represents all unix users.

List resource
+++++++++++++

.. http:get:: /api/v1.0/account/bsdusers/

   Returns a list of all current users.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/account/bsdusers/ HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: text/javascript

      [
        {
                'bsdusr_builtin': true,
                'bsdusr_email': '',
                'bsdusr_full_name': 'root',
                'bsdusr_group': 0,
                'bsdusr_home': '/root',
                'bsdusr_locked': false,
                'bsdusr_password_disabled': false,
                'bsdusr_shell': '/bin/csh',
                'bsdusr_smbhash': 'root:0:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX:E6FCEFB62A365065CE5B5F04AB12B455:[U          ]:LCT-52272D9E:',
                'bsdusr_uid': 0,
                'bsdusr_unixhash': '$6$d8doVGxjhDhL4feI$YpTtmlhCmbc6BJ4MQcBsPvZA0Ge4SMnAyZn9CfZLpkuP71g8bPq6DkKJBmcN61z2oQSj0K8RtaqmKltc9HsMg0',
                'bsdusr_username': 'root',
                'id': 1
        }
      ]

   :query offset: offset number. default is 0
   :query limit: limit number. default is 30
   :resheader Content-Type: content type of the response
   :statuscode 200: no error


Create resource
+++++++++++++++

.. http:post:: /api/v1.0/account/bsdusers/

   Creates a new user and returns the new user object.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/account/bsdusers/ HTTP/1.1
      Accept: application/json, text/javascript

        {
                'bsdusr_username': 'myuser',
                'bsdusr_creategroup': True,
                'bsdusr_full_name': 'haha',
                'bsdusr_password': 'aa',
                'bsdusr_uid': 1111
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 201 Created
      Vary: Accept
      Content-Type: text/javascript

      [
        {
                'bsdusr_builtin': false,
                'bsdusr_email': '',
                'bsdusr_full_name': 'My User',
                'bsdusr_group': 0,
                'bsdusr_home': '/nonexistent',
                'bsdusr_locked': false,
                'bsdusr_password_disabled': false,
                'bsdusr_shell': '/bin/csh',
                'bsdusr_smbhash': 'myuser:0:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX:E6FCEFB62A365065CE5B5F04AB12B455:[U          ]:LCT-52272D9E:',
                'bsdusr_uid': 0,
                'bsdusr_unixhash': '$6$d8doVGxjhDhL4feI$YpTtmlhCmbc6BJ4MQcBsPvZA0Ge4SMnAyZn9CfZLpkuP71g8bPq6DkKJBmcN61z2oQSj0K8RtaqmKltc9HsMg0',
                'bsdusr_username': 'myuser',
                'id': 25
        }
      ]

   :json string bsdusr_username: unix username
   :json string bsdusr_full_name: name of the user
   :json string bsdusr_password: password for the user
   :json integer bsdusr_uid: unique user id
   :json integer bsdusr_group: id of the group object
   :json boolean bsdusr_creategroup: create a group for the user
   :json string bsdusr_mode: unix mode to set the homedir
   :json string bsdusr_shell: shell for the user login
   :reqheader Content-Type: the request content type
   :resheader Content-Type: the response content type
   :statuscode 201: no error


Delete resource
+++++++++++++++


.. http:delete:: /api/v1.0/account/bsdusers/(int:id)/

   Delete a user of `id`.

   **Example request**:

   .. sourcecode:: http

      DELETE /api/v1.0/account/bsdusers/25/ HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 204 No Response
      Vary: Accept
      Content-Type: text/javascript

   :statuscode 204: no error


Change password
+++++++++++++++


.. http:post:: /api/v1.0/account/bsdusers/(int:id)/password/

   Change password of user `id`.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/account/bsdusers/25/password/ HTTP/1.1
      Accept: application/json, text/javascript

        {
                "bsdusr_password": "newpasswd"
        }

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: text/javascript

        {
                'bsdusr_builtin': false,
                'bsdusr_email': '',
                'bsdusr_full_name': 'My User',
                'bsdusr_group': 0,
                'bsdusr_home': '/nonexistent',
                'bsdusr_locked': false,
                'bsdusr_password_disabled': false,
                'bsdusr_shell': '/bin/csh',
                'bsdusr_smbhash': 'myuser:0:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX:E6FCEFB62A365065CE5B5F04AB12B455:[U          ]:LCT-52272D9E:',
                'bsdusr_uid': 0,
                'bsdusr_unixhash': '$6$d8doVGxjhDhL4feI$YpTtmlhCmbc6BJ4MQcBsPvZA0Ge4SMnAyZn9CfZLpkuP71g8bPq6DkKJBmcN61z2oQSj0K8RtaqmKltc9HsMg0',
                'bsdusr_username': 'myuser',
                'id': 25
        }

   :json string bsdusr_password: new password
   :statuscode 200: no error


Get user groups
++++++++++++++++

.. http:get:: /api/v1.0/account/bsdusers/(int:id)/groups/

   Get a list of groups of user `id`.

   **Example request**:

   .. sourcecode:: http

      GET /api/v1.0/account/bsdusers/25/groups/ HTTP/1.1
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 200 OK
      Vary: Accept
      Content-Type: text/javascript

        []

   :statuscode 200: no error


Set user groups
++++++++++++++++

.. http:post:: /api/v1.0/account/bsdusers/(int:id)/groups/

   Set a list of groups of user `id`.

   **Example request**:

   .. sourcecode:: http

      POST /api/v1.0/account/bsdusers/25/groups/ HTTP/1.1
      Accept: application/json, text/javascript

        [
                "wheel",
                "ftp"
        ]

   **Example response**:

   .. sourcecode:: http

      HTTP/1.1 202 Accepted
      Vary: Accept
      Content-Type: text/javascript

        [
                "wheel",
                "ftp"
        ]

   :statuscode 202: no error
