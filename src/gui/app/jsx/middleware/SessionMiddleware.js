// Session Middleware
// ================
// TODO: Decide whether we need this or not


"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

module.exports = {

    subscribe: function() {
      MiddlewareClient.subscribe( ["server.client_connected"] );
    }

  , unsubscribe: function() {
      MiddlewareClient.unsubscribe( ["server.client_connected"] );
    }

};