// Update Data Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");
var UpdateActionCreators = require("../actions/SystemActionCreators");

module.exports = {

   requestUpdateInfo: function(updateInfoName) {
   	  console.log(updateInfoName);
      MiddlewareClient.request( "update." + updateInfoName,  [], function ( updateInfo ) {
        UpdateActionCreators.receiveUpdateInfo( updateInfo, updateInfoName );
      });
  }

};
