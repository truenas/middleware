// Services Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class ServicesActionCreators {

  receiveServicesList ( rawServices ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RAW_SERVICES
      , rawServices: rawServices
      }
    );
  }

  receiveServiceUpdateTask ( taskID, serviceName ) {
    FreeNASDispatcher.handleClientAction(
      { type: ActionTypes.RECEIVE_SERVICE_UPDATE_TASK
      , taskID: taskID
      , serviceName: serviceName
      }
    );
  }

};

export default new ServicesActionCreators();
