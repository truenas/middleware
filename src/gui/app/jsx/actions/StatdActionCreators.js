// Widget Data Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class StatdActionCreators {

  static receiveWidgetData ( dataSourceName, rawWidgetData, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RAW_WIDGET_DATA
      , dataSourceName
      , rawWidgetData
      , timestamp
      }
    );
  }

};

export default StatdActionCreators;
