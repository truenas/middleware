// System.Info Action Creators
// ==================================

"use strict";

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes = FreeNASConstants.ActionTypes;

module.exports = {

    receiveSystemInfo: function( systemInfo, systemInfoName ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        		: ActionTypes.RECEIVE_SYSTEM_INFO_DATA
        , systemInfo 		: systemInfo
        , systemInfoName 	: systemInfoName
      });
    }

};
