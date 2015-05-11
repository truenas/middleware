// Widget Data Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

module.exports = {

  receiveWidgetData: function ( rawWidgetData, dataSourceName ) {
    FreeNASDispatcher.handleMiddlewareAction({
        type        : ActionTypes.RECEIVE_RAW_WIDGET_DATA
      , rawWidgetData : rawWidgetData
      , dataSourceName : dataSourceName
    });
  }

};
