// Power Middleware
// ================
// Provides abstraction functions that queue systems tasks to the middleware i.e. shutdown,reboot, etc 

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

module.exports = {
   reboot: function() {
      MiddlewareClient.request( "task.submit", ["system.reboot", ""]);
    },

   shutdown: function() {
      MiddlewareClient.request( "task.submit", ["system.shutdown", ""]);
   }

};
