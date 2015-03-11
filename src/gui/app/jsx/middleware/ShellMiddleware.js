// Shell Middleware
// ================
// Utility methods for accessing shells through the Middleware Server.

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

module.exports = {

    requestAvailableShells: function( callback ) {
      MiddlewareClient.request( "shell.get_shells", null, callback );
    }

  , spawnShell: function( shellType, callback ) {
      MiddlewareClient.request( "shell.spawn", [ shellType ], callback );
    }
};
