// Updater Middleware
// ================
// Provides abstraction functions to use freenas's updater in the rest
// of the GUI

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

// import UpdaterActionCreators from "../actions/UpdaterActionCreators";

class UpdaterMiddleware extends AbstractBase {

  static subscribe ( componentID ) {
    MC.subscribe( [ "update.in_progress", "update.changed" ], componentID );
  }

  static unsubscribe ( componentID ) {
    MC.unsubscribe( [ "update.in_progress", "update.changed" ], componentID );
  }

  static updatenow ( ) {
    MC.request( "task.submit", [ "update.update", "" ] );
  }

  static getConfig ( callback ) {
    MC.request( "update.get_config"
              , []
              , callback
              );
  }

  static checkForUpdate () {
    MC.request( "task.submit", [ "update.check", [] ] );
  }
};

export default UpdaterMiddleware;
