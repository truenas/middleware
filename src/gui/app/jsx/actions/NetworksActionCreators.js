// Networks Action Creators
// =======================

"use strict";

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes = FreeNASConstants.ActionTypes;

module.exports = {

    receiveNetworksList: function( rawNetworksList ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type            : ActionTypes.RECEIVE_RAW_NETWORKS
        , rawNetworksList : rawNetworksList
      });
    }

};
