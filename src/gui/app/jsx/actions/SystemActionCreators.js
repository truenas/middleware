// System.Info Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class SystemActionCreators {

  static receiveSystemInfo ( systemInfo, systemInfoName, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_SYSTEM_INFO_DATA
      , timestamp
      , systemInfo
      , systemInfoName
      }
    );
  }

  static receiveSystemDevice ( systemDevice, systemDeviceArgument, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_SYSTEM_DEVICE_DATA
      , timestamp
      , systemDevice
      , systemDeviceArgument
      }
    );
  }

};

export default SystemActionCreators;
