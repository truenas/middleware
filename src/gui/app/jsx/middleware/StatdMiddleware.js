// Widget Data Middleware
// ===================

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var StatdActionCreators = require("../actions/StatdActionCreators");

module.exports = {

    subscribe: function(  componentID, dataSourceName ) {
      MiddlewareClient.subscribe( ["statd." + dataSourceName + ".pulse"], componentID );
    }

  , unsubscribe: function(  componentID, dataSourceName ) {
      MiddlewareClient.unsubscribe( ["statd." + dataSourceName + ".pulse"], componentID );
    }

  , requestWidgetData: function(dataSourceName, startIsoTimestamp, endIsoTimestamp, frequency) {
      MiddlewareClient.request( "statd.output.query", [dataSourceName, {"start": startIsoTimestamp, "end": endIsoTimestamp, "frequency": frequency}], function ( rawWidgetData ) {
        StatdActionCreators.receiveWidgetData( rawWidgetData, dataSourceName );
      });
  }

};
