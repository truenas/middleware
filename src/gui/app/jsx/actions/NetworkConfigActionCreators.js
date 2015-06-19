// Network Config Action Creators
// ==============================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class NetworkConfigActionCreators {

  static receiveNetworkConfig ( networkConfig, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_NETWORK_CONFIG
      , timestamp
      , networkConfig
      }
    );
  }

  static receiveNetworkUpdateTask ( taskID, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_NETWORK_CONFIG_UPDATE
      , timestamp
      , taskID
      }
    );
  }

};

export default NetworkConfigActionCreators;
