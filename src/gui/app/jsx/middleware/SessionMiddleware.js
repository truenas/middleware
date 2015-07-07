// Session Middleware
// ================

"use strict";

import _ from "lodash";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

import SAC from "../actions/SessionActionCreators";

class SessionsMiddleware extends AbstractBase {

  static getLiveUserSessions ( successCallback, errorCallback ) {
    MC.request( "sessions.get_live_user_sessions"
              , []
              , successCallback
              );
  }

  static kickUserSession ( sessionID, successCallback, errorCallback ) {
    MC.request( "management.kick_session"
              , [ sessionID ]
              , successCallback
              , errorCallback
              );
  }

};

export default SessionsMiddleware;
