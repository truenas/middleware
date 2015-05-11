// CLIENT STATUS MIXIN
// ===================
// This mixin contains a set of common helper methods which may be used to
// reduce the amount of boilerplate code in views which depend on some aspect
// of the FreeNAS webapp having a certain state - for example, being logged in.

"use strict";

import SessionStore from "../../stores/SessionStore";

module.exports = {

    getInitialState: function () {
        return {
          SESSION_AUTHENTICATED: SessionStore.getLoginStatus()
        };
      }

  , componentDidMount: function () {
        SessionStore.addChangeListener( this.handleSessionChange );
      }

  , handleSessionChange: function () {
        this.setState({ SESSION_AUTHENTICATED: SessionStore.getLoginStatus() });
      }

};
