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
              , SAC.receiveSystemInfo.bind( SAC )
              );
  }

  static requestSystemDevice ( arg ) {
    MC.request( "system.device.get_devices"
              , [ arg ]
              , SAC.receiveSystemDevice.bind( SAC )
              );
  }

};

export default SystemMiddleware;
