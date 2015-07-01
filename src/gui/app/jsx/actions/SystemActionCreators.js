// System.Info Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class SystemActionCreators {

  static receiveSystemInfo ( systemInfoName, systemInfo, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_SYSTEM_INFO_DATA
      , timestamp
      , systemInfo
      , systemInfoName
      }
    );
  }

  static receiveSystemDevice ( systemDeviceArgument, systemDevice, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_SYSTEM_DEVICE_DATA
      , timestamp
      , systemDevice
      , systemDeviceArgument
      }
    );
  }

  static receiveSystemGeneralConfig ( config, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_SYSTEM_GENERAL_CONFIG_DATA
      , timestamp
      , config }
    );
  }

  static receiveSystemGeneralConfigUpdateTask ( taskID, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_SYSTEM_GENERAL_CONFIG_UPDATE
      , timestamp
      , taskID
      }
    );
  }

};

export default SystemActionCreators;
