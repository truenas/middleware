// Update Middleware
// ================
// Provides abstraction functions to use freenas's updater in the rest of the GUI

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

module.exports = {
   updatenow: function() {
      MiddlewareClient.request( "task.submit", ["update.update", ""]);
    }

};