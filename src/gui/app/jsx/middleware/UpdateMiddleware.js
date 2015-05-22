// Update Middleware
// ================
// Provides abstraction functions to use freenas's updater in the rest of the GUI

"use strict";

import MiddlewareClient from "./MiddlewareClient";

module.exports = {
   updatenow: function () {
      MiddlewareClient.request( "task.submit", ["update.update", ""]);
    }

};