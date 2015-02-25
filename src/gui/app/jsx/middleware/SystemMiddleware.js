// System Info Data Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");
var SystemActionCreators = require("../actions/SystemActionCreators");

module.exports = {

   requestSystemInfo: function(systemInfoName) {
   	  console.log(systemInfoName);
      MiddlewareClient.request( "system.info." + systemInfoName,  [], function ( systemInfo ) {
        SystemActionCreators.receiveSystemInfo( systemInfo, systemInfoName );
      });
  }

};
