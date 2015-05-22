// Widget Data Middleware
// ===================

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

import SAC from "../actions/StatdActionCreators";

function createPulseSyntax ( dataSource ) {
  return "statd." + dataSource + ".pulse";
};

class StatdMiddleware extends AbstractBase {

  static subscribeToPulse ( componentID, dataSources ) {
    MC.subscribe( dataSources.map( createPulseSyntax ), componentID );
  }

  static unsubscribeFromPulse ( componentID, dataSources ) {
    MC.unsubscribe( dataSources.map( createPulseSyntax ), componentID );
  }

  static requestWidgetData ( sourceName, startTime, endTime, freq ) {
    MC.request( "statd.output.query"
              , [ sourceName
                , { start: startTime
                  , end: endTime
                  , frequency: freq
                  }
                ]
              , function handleWidgetData ( rawWidgetData ) {
                  SAC.receiveWidgetData( rawWidgetData, sourceName );
                }
              );
  }

};

export default StatdMiddleware;
