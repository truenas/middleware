// Sessions Action Creators
// =====================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class SessionActionCreators {

  static forceLogout ( message, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.FORCE_LOGOUT
      , timestamp
      , message
      }
    );
  }

};

export default SessionActionCreators;
