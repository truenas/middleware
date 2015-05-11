// Session Middleware
// ================
// TODO: Decide whether we need this or not

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";

module.exports = {

    subscribe: function( componentID ) {
      MiddlewareClient.subscribe( ["server.client_connected"], componentID );
    }

  , unsubscribe: function( componentID ) {
      MiddlewareClient.unsubscribe( ["server.client_connected"], componentID );
    }

};