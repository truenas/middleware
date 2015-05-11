// Networks Action Creators
// =======================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

module.exports = {

    receiveNetworksList: function( rawNetworksList ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type            : ActionTypes.RECEIVE_RAW_NETWORKS
        , rawNetworksList : rawNetworksList
      });
    }

};
