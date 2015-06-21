// Shell Middleware
// ================
// Utility methods for accessing shells through the Middleware Server.

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

class ShellMiddleware extends AbstractBase {

  static requestAvailableShells ( callback ) {
    MC.request( "shell.get_shells", null, callback );
  }

  static spawnShell ( shellType, callback ) {
    MC.request( "shell.spawn", [ shellType ], callback );
  }

};

export default ShellMiddleware;
