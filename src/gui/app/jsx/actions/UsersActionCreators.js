// Users Action Creators
// ==================================
// Receive and handle events from the middleware, and call the dispatcher.

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

module.exports = {

  receiveUsersList: function ( rawUsers ) {
      FreeNASDispatcher.handleMiddlewareAction({
        type     : ActionTypes.RECEIVE_RAW_USERS
        , rawUsers : rawUsers
      });
    }

  , receiveUserUpdateTask: function ( taskID, userID ) {
      FreeNASDispatcher.handleClientAction({
        type   : ActionTypes.RECEIVE_USER_UPDATE_TASK
        , taskID : taskID
        , userID : userID
      });
    }

};
