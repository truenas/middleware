// Update Action Creators
// ==================================

"use strict";

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes = FreeNASConstants.ActionTypes;

module.exports = {

    receiveUpdateInfo: function( updateInfo, updateInfoName ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        		: ActionTypes.RECEIVE_UPDATE_DATA
        , updateInfo 		: updateInfo
        , updateInfoName 	: updateInfoName
      });
    }

};
