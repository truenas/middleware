// Services Action Creators
// ==================================

"use strict";

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes = FreeNASConstants.ActionTypes;

module.exports = {

    receiveServicesList: function( rawServices ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        : ActionTypes.RECEIVE_RAW_SERVICES
        , rawServices : rawServices
      });
    }

  , receiveServiceUpdateTask: function( taskID, serviceName ) {
      FreeNASDispatcher.handleClientAction({
          type  	  : ActionTypes.RECEIVE_SERVICE_UPDATE_TASK
        , taskID 	  : taskID
        , serviceName : serviceName
      });
    }

};
