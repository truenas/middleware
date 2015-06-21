// Disks Action Creators
// =====================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class DisksActionCreators {

  static receiveDisksOverview ( disksOverview, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_DISKS_OVERVIEW
      , timestamp
      , disksOverview
      }
    );
  }

  static receiveDiskDetails ( diskDetails, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_DISK_DETAILS
      , timestamp
      , diskDetails
      , diskID: diskDetails[ "serial" ]
      }
    );
  }

};

export default DisksActionCreators;
