// Tasks Action Creators
// =====================
// Handle any Task data being sent from middleware which is NOT covered by the
// standard MIDDLEWARE_EVENT action.

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class TasksActionCreators {

  static receiveTaskHistory ( tasks ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_TASK_HISTORY
      , tasks: tasks
      }
    );
  }

};

export default TasksActionCreators;
