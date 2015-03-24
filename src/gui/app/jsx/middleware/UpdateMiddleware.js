// Update Data Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");
var UpdateActionCreators = require("../actions/UpdateActionCreators");

module.exports = {

   requestUpdateInfo: function(updateInfoName) {
      MiddlewareClient.request( "update." + updateInfoName,  [], function ( updateInfo ) {
        UpdateActionCreators.receiveUpdateInfo( updateInfo, updateInfoName );
      });
  }

};
