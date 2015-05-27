// System.Info Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class SystemActionCreators {

  static receiveSystemInfo ( systemInfo, systemInfoName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_SYSTEM_INFO_DATA
      , systemInfo: systemInfo
      , systemInfoName: systemInfoName
      }
    );
  }

  static receiveSystemDevice ( systemDevice, systemDeviceArgument ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_SYSTEM_DEVICE_DATA
      , systemDevice: systemDevice
      , systemDeviceArgument: systemDeviceArgument
      }
    );
  }

};

export default SystemActionCreators;
