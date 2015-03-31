// Power Middleware
// ================
// Provides abstraction functions that queue systems tasks to the middleware i.e. shutdown,reboot, etc

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

// Cookies!
var myCookies = require("./cookies");

module.exports = {

    subscribe: function( componentID ) {
      MiddlewareClient.subscribe( ["power.changed", "update.changed"], componentID );
    }

  , unsubscribe: function( componentID ) {
      MiddlewareClient.unsubscribe( ["power.changed", "update.changed"], componentID );
    }

  , reboot: function() {
      MiddlewareClient.request( "task.submit", ["system.reboot", ""]);
      myCookies.delete("auth");
    }

  , shutdown: function() {
      MiddlewareClient.request( "task.submit", ["system.shutdown", ""]);
      myCookies.delete("auth");
   }

};
