// Users Action Creators
// ==================================
// Receive and handle events from the middleware, and call the dispatcher.

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class UsersActionCreators {

  static receiveUsersList ( rawUsers, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RAW_USERS
      , timestamp
      , rawUsers
      }
    );
  }

  static receiveUserUpdateTask ( taskID, userID, timestamp ) {
    FreeNASDispatcher.handleClientAction(
      { type: ActionTypes.RECEIVE_USER_UPDATE_TASK
      , timestamp
      , taskID
      , userID
      }
    );
  }

};

export default UsersActionCreators;
