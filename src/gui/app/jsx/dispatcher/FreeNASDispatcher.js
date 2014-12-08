// FreeNAS Dispatcher
// ------------------
// Flux dispatcher used throughout the FreeNAS webapp. Manages all data flow,
// updates data stores with new data from user interaction or from the
// middleware.

"use strict";

var _                 = require("lodash");
var Dispatcher        = require("flux").Dispatcher;
var FreeNASConstants  = require("../constants/FreeNASConstants");
var PayloadSources    = FreeNASConstants.PayloadSources;

var FreeNASDispatcher = _.assign( new Dispatcher(), {

    handleMiddlewareAction: function( action ) {
      var payload = {
          source : PayloadSources.MIDDLEWARE_ACTION
        , action : action
      };

      this.dispatch( payload );
    }

  , handleMiddlewareLifecycle: function( action ) {
      var payload = {
          source : PayloadSources.MIDDLEWARE_LIFECYCLE
        , action : action
      };

      this.dispatch( payload );
  }

  , handleClientAction: function( action ) {
      var payload = {
          source : PayloadSources.CLIENT_ACTION
        , action : action
      };

      this.dispatch( payload );
  }
});

module.exports = FreeNASDispatcher;
