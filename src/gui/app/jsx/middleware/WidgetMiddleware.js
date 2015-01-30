// Widget Data Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var WidgetActionCreators = require("../actions/WidgetActionCreators");

module.exports = {

  requestWidgetData: function(dataSourceName, startIsoTimestamp, endIsoTimestamp, frequency) {
      MiddlewareClient.request( "statd.output.query",  [dataSourceName, {"start": startIsoTimestamp, "end": endIsoTimestamp, "frequency": frequency}], function ( rawWidgetData ) {
        WidgetActionCreators.receiveServicesList( rawWidgetData );
      });
  }

};
