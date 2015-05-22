// System Info Data Middleware
// ===================

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";
import SAC from "../actions/SystemActionCreators";

class SystemMiddleware extends AbstractBase {

  static requestSystemInfo ( namespace ) {
    MC.request( "system.info." + namespace
              , []
              , function handleSystemInfo ( systemInfo ) {
                  SAC.receiveSystemInfo( systemInfo, namespace );
                }
              );
  }

  static requestSystemDevice ( arg ) {
    MC.request( "system.device.get_devices"
              , [ arg ]
              , function handleSystemDevice ( systemDevice ) {
                  SAC.receiveSystemDevice( systemDevice, arg );
                }
              );
  }

};

export default SystemMiddleware;
