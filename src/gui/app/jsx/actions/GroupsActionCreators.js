// Groups Action Creators
// ==================================
// Receive and handle events from the middleware, and call the dispatcher.

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class GroupsActionCreators {

  static receiveGroupsList ( groupsList, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_GROUPS_LIST
      , timestamp
      , groupsList
      }
    );
  }

  static receiveGroupUpdateTask ( taskID, groupID, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_GROUP_UPDATE_TASK
      , timestamp
      , taskID
      , groupID
      }
    );
  }

};

export default GroupsActionCreators;
