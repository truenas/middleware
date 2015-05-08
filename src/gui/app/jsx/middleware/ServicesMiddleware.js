// Services Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var ServicesActionCreators = require("../actions/ServicesActionCreators");

module.exports = {

    subscribeToTask: function( componentID ) {
      MiddlewareClient.subscribe( ["task.*"], componentID );
    }

  , unsubscribeFromTask: function( componentID ) {
      MiddlewareClient.unsubscribe( ["task.*"], componentID );
    }

  , updateService: function( serviceName, action ) {
      MiddlewareClient.request( "task.submit", ["service.manage", [ serviceName, action ] ], function ( taskID ) {
        ServicesActionCreators.receiveServiceUpdateTask( taskID, serviceName );
      });
    }

  , requestServicesList: function() {
      MiddlewareClient.request( "services.query", [], function ( rawServicesList ) {
        ServicesActionCreators.receiveServicesList( rawServicesList );
      });
  }

};
