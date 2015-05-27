// Update Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class UpdateActionCreators {

  static receiveUpdateInfo ( updateInfo, updateInfoName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_UPDATE_DATA
      , updateInfo: updateInfo
      , updateInfoName: updateInfoName
      }
    );
  }

};

export default UpdateActionCreators;
