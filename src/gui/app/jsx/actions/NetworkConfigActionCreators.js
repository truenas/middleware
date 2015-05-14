// Network Config Action Creators
// ==============================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class NetworkConfigActionCreators {

  receiveNetworkConfig ( networkConfig ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_NETWORK_CONFIG
      , networkConfig: networkConfig
      }
    );
  }

  receiveNetworkUpdateTask ( taskID ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_NETWORK_CONFIG_UPDATE
      , taskID: taskID
      }
    );
  }

};

export default new NetworkConfigActionCreators ();
