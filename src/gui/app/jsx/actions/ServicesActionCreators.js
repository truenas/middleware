// Services Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

module.exports = {

    receiveServicesList: function( rawServices ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        : ActionTypes.RECEIVE_RAW_SERVICES
        , rawServices : rawServices
      });
    }

  , receiveServiceUpdateTask: function( taskID, serviceName ) {
      FreeNASDispatcher.handleClientAction({
          type  	  : ActionTypes.RECEIVE_SERVICE_UPDATE_TASK
        , taskID 	  : taskID
        , serviceName : serviceName
      });
    }

};
