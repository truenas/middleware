// Tasks Action Creators
// =====================
// Handle any Task data being sent from middleware which is NOT covered by the
// standard MIDDLEWARE_EVENT action.

"use strict";

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes = FreeNASConstants.ActionTypes;

module.exports = {

    receiveTaskHistory: function ( tasks ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type  : ActionTypes.RECEIVE_TASK_HISTORY
        , tasks : tasks
      });
    }

};
