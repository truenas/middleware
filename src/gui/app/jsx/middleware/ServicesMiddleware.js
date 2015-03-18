// Services Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var ServicesActionCreators = require("../actions/ServicesActionCreators");

module.exports = {

  requestServicesList: function() {
      MiddlewareClient.request( "services.query", [], function ( rawServicesList ) {
        ServicesActionCreators.receiveServicesList( rawServicesList );
      });
  }

};
