// Update Middleware
// ================
// Provides abstraction functions to use freenas's updater in the rest
// of the GUI

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

class UpdateMiddleware extends AbstractBase {

  static updatenow () {
    MC.request( "task.submit", [ "update.update", "" ] );
  }

};

export default UpdateMiddleware;
