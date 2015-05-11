// System Info Data Middleware
// ===================

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";
import SystemActionCreators from "../actions/SystemActionCreators";

module.exports = {

   requestSystemInfo: function(systemInfoName) {
      MiddlewareClient.request( "system.info." + systemInfoName,  [], function ( systemInfo ) {
        SystemActionCreators.receiveSystemInfo( systemInfo, systemInfoName );
      });
  }

 , requestSystemDevice: function(systemDeviceArgument) {
      MiddlewareClient.request( "system.device.get_devices",  [systemDeviceArgument], function ( systemDevice ) {
        SystemActionCreators.receiveSystemDevice( systemDevice, systemDeviceArgument );
      });
  }

};
