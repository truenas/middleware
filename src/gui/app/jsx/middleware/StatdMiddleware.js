// Widget Data Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var StatdActionCreators = require("../actions/StatdActionCreators");

module.exports = {

    subscribe: function( dataSourceName ) {
      MiddlewareClient.subscribe( ["statd." + dataSourceName + ".pulse"] );
    }

  , unsubscribe: function( dataSourceName ) {
      MiddlewareClient.unsubscribe( ["statd." + dataSourceName + ".pulse"] );
    }

  , requestWidgetData: function(dataSourceName, startIsoTimestamp, endIsoTimestamp, frequency) {
      MiddlewareClient.request( "statd.output.query", [dataSourceName, {"start": startIsoTimestamp, "end": endIsoTimestamp, "frequency": frequency}], function ( rawWidgetData ) {
        StatdActionCreators.receiveWidgetData( rawWidgetData, dataSourceName );
      });
  }

};
