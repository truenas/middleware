// Update Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class UpdateActionCreators {

  static receiveUpdateInfo ( updateInfo, updateInfoName, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_UPDATE_DATA
      , timestamp
      , updateInfo
      , updateInfoName
      }
    );
  }

};

export default UpdateActionCreators;
