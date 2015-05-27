// Interfaces Action Creators
// ==========================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class InterfacesActionCreators {

  static receiveInterfacesList ( rawInterfacesList ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_INTERFACES_LIST
      , rawInterfacesList: rawInterfacesList
      }
    );
  }

};

export default InterfacesActionCreators;
