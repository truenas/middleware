// Widget Data Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class StatdActionCreators {

  static receiveWidgetData ( rawWidgetData, dataSourceName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_RAW_WIDGET_DATA
      , rawWidgetData: rawWidgetData
      , dataSourceName: dataSourceName
      }
    );
  }

};

export default StatdActionCreators;
