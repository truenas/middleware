// Widget Data Middleware
// ===================

"use strict";

import MiddlewareClient from "./MiddlewareClient";

import StatdActionCreators from "../actions/StatdActionCreators";

var createPulseSyntax = function ( dataSource ) {
  return "statd." + dataSource + ".pulse";
};

module.exports = {

    subscribeToPulse: function ( componentID, dataSourceArray ) {
      MiddlewareClient.subscribe( dataSourceArray.map( createPulseSyntax ), componentID );
    }

  , unsubscribeFromPulse: function ( componentID, dataSourceArray ) {
      MiddlewareClient.unsubscribe( dataSourceArray.map( createPulseSyntax ), componentID );
    }

  , requestWidgetData: function ( dataSourceName, startIsoTimestamp, endIsoTimestamp, frequency ) {
      MiddlewareClient.request( "statd.output.query", [ dataSourceName, {"start": startIsoTimestamp, "end": endIsoTimestamp, "frequency": frequency}], function ( rawWidgetData ) {
        StatdActionCreators.receiveWidgetData( rawWidgetData, dataSourceName );
      });
  }

};
