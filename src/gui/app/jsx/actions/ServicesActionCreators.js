// Services Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class ServicesActionCreators {

  static receiveServicesList ( rawServices, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RAW_SERVICES
      , timestamp
      , rawServices
      }
    );
  }

  static receiveServiceUpdateTask ( serviceName, taskID, timestamp ) {
    FreeNASDispatcher.handleClientAction(
      { type: ActionTypes.RECEIVE_SERVICE_UPDATE_TASK
      , timestamp
      , taskID
      , serviceName
      }
    );
  }

};

export default ServicesActionCreators;
