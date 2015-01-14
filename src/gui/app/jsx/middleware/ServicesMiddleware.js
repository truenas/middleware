// Services Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var ServicesActionCreators = require("../actions/ServicesActionCreators");

module.exports = {

  requestServicesList: function() {
      MiddlewareClient.request( "service.query", [], function ( rawServicesList ) {
        ServicesActionCreators.receiveServicesList( rawServicesList );
      });
  }

};
