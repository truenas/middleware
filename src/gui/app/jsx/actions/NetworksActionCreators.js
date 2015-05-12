// Networks Action Creators
// =======================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class NetworksActionCreators {

  receiveNetworksList ( rawNetworksList ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RAW_NETWORKS
      , rawNetworksList: rawNetworksList
      }
    );
  }

};

export default new NetworksActionCreators();
