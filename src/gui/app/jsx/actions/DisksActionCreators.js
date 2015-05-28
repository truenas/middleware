// Disks Action Creators
// =====================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class DisksActionCreators {

  static receiveDisksOverview ( disksOverview ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_DISKS_OVERVIEW
      , disksOverview: disksOverview
      }
    );
  }

  static receiveDiskDetails ( diskDetails ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_DISK_DETAILS
      , diskID: diskDetails[ "serial" ]
      , diskDetails: diskDetails
      }
    );
  }

};

export default DisksActionCreators;
