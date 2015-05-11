// Update Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

module.exports = {

    receiveUpdateInfo: function( updateInfo, updateInfoName ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        		: ActionTypes.RECEIVE_UPDATE_DATA
        , updateInfo 		: updateInfo
        , updateInfoName 	: updateInfoName
      });
    }

};
