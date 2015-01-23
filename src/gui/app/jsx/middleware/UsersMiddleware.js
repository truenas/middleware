// Users Middleware
// ================
// Handle the lifecycle and event hooks for the Users channel of the middleware

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var UsersActionCreators = require("../actions/UsersActionCreators");

module.exports = {

    subscribe: function() {
      MiddlewareClient.subscribe( ["users.changed"] );
    }

  , unsubscribe: function() {
      MiddlewareClient.unsubscribe( ["users.changed"] );
    }

  , requestUsersList: function( ids ) {
      MiddlewareClient.request( "users.query", ( ids ? [[[ "id", "in", ids ]]] : [] ), function ( rawUsersList ) {
        UsersActionCreators.receiveUsersList( rawUsersList );
      });
    }

  , updateUser: function( userID, changedProps ) {
      MiddlewareClient.request( "task.submit", ["users.update", [ userID, changedProps ] ], function ( taskID ) {
        UsersActionCreators.receiveUserUpdateTask( taskID, userID );
      });
    }

};
