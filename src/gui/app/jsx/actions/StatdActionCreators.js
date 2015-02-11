// Widget Data Action Creators
// ==================================

"use strict";

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var ActionTypes = FreeNASConstants.ActionTypes;

module.exports = {

    receiveWidgetData: function( rawWidgetData, dataSourceName ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        : ActionTypes.RECEIVE_RAW_WIDGET_DATA
        , rawWidgetData : rawWidgetData
        , dataSourceName : dataSourceName
      });
    }

};
