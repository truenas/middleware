// Power Middleware
// ================
// Provides abstraction functions that queue systems tasks to the middleware
// i.e. shutdown, reboot, etc

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

// Cookies!
import myCookies from "./cookies";

class PowerMiddleware extends AbstractBase {

  static subscribe ( componentID ) {
    MC.subscribe( [ "power.changed", "update.changed" ], componentID );
  }

  static unsubscribe ( componentID ) {
    MC.unsubscribe( [ "power.changed", "update.changed" ], componentID );
  }

  static reboot  () {
    MC.request( "task.submit"
              , [ "system.reboot", "" ]
              , function handleReboot () {
                  myCookies.delete( "auth" );
                }
              );
  }

  static shutdown  () {
    MC.request( "task.submit"
              , [ "system.shutdown", "" ]
              , function handleShutdown () {
                  myCookies.delete( "auth" );
                }
              );
  }

};

export default PowerMiddleware;
