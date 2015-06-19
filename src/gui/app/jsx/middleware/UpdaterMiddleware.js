// Updater Middleware
// ================
// Provides abstraction functions to use freenas's updater in the rest
// of the GUI

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

// import UpdaterActionCreators from "../actions/UpdaterActionCreators";

class UpdaterMiddleware extends AbstractBase {

  static updatenow () {
    MC.request( "task.submit", [ "update.update", "" ] );
  }
  static getConfig ( callback ) {
    MC.request( "update.get_config"
              , []
              , callback
              );
  }
};

export default UpdaterMiddleware;
