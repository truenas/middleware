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

};
