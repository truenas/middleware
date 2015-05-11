// Update Data Middleware
// ===================

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";
import UpdateActionCreators from "../actions/UpdateActionCreators";

module.exports = {

   requestUpdateInfo: function(updateInfoName) {
      MiddlewareClient.request( "update." + updateInfoName,  [], function ( updateInfo ) {
        UpdateActionCreators.receiveUpdateInfo( updateInfo, updateInfoName );
      });
  }

};
