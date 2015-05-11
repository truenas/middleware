// System.Info Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

module.exports = {

    receiveSystemInfo: function( systemInfo, systemInfoName ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        		: ActionTypes.RECEIVE_SYSTEM_INFO_DATA
        , systemInfo 		: systemInfo
        , systemInfoName 	: systemInfoName
      });
    }

  , receiveSystemDevice: function( systemDevice, systemDeviceArgument ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        			: ActionTypes.RECEIVE_SYSTEM_DEVICE_DATA
        , systemDevice 			: systemDevice
        , systemDeviceArgument 	: systemDeviceArgument
      });

  }

};
