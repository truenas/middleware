// Services Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var ServicesActionCreators = require("../actions/ServicesActionCreators");

module.exports = {

  updateService: function( serviceName, action ) {
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
