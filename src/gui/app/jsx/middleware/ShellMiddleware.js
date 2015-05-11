// Shell Middleware
// ================
// Utility methods for accessing shells through the Middleware Server.

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";

module.exports = {

    requestAvailableShells: function( callback ) {
      MiddlewareClient.request( "shell.get_shells", null, callback );
    }

  , spawnShell: function( shellType, callback ) {
      MiddlewareClient.request( "shell.spawn", [ shellType ], callback );
    }
};
