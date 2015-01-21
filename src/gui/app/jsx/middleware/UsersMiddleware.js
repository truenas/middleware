// Users Middleware
// ================
// Handle the lifecycle and event hooks for the Users channel of the middleware

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var UsersActionCreators = require("../actions/UsersActionCreators");

module.exports = {

    subscribe: function() {
      MiddlewareClient.subscribe( ["users.changed"], function ( changedIDs ) {
        UsersActionCreators.receiveChangedIDs( changedIDs );
      });
    }

  , unsubscribe: function() {
      MiddlewareClient.unsubscribe( ["users.changed"] );
    }

  , requestUsersList: function() {
      MiddlewareClient.request( "users.query", [], function ( rawUsersList ) {
        UsersActionCreators.receiveUsersList( rawUsersList );
      });
    }

};
