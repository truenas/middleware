

"use strict";

var React            =   require( "react" );

var chartHandler     =   require( "./mixins/chartHandler" );

var round            =   require( "round" );

var SystemLoad = React.createClass({

  mixins: [ chartHandler ]

  , getInitialState: function () {
    return {
      statdResources:    [   { variable: "longterm"
                               , dataSource: "localhost.load.load.longterm"
                               , name: "Longterm Load"
                               , color: "#292929"}
                           , { variable: "midterm"
                               , dataSource: "localhost.load.load.midterm"
                               , name: "Midterm Load"
                               , color: "#a47f1a"}
                           , { variable: "shortterm"
                               , dataSource: "localhost.load.load.shortterm"
                               , name: "Shortterm Load"
                               , color: "#4a95b3"}
                         ]
      , chartTypes:      [  {   type: "line"
                              , primary: this.primaryChart( "line" )
                              , y: function ( d ) {
                                return ( round( d[1], 0.01 ) );
                              }
                            }
                          , {   type: "stacked"
                              , primary: this.primaryChart( "stacked" )
                              , y: function ( d ) {
                                return ( round( d[1], 0.01 ) );
                              }
                            }
                         ]
      , widgetIdentifier : "SystemLoad"
    };
  }

  , primaryChart: function ( type ) {
    if ( this.props.primary === undefined && type === "line" ) {
      return true;
    } else if ( type === this.props.primary ) {
      return true;
    } else {
      return false;
    }

  }
});


module.exports = SystemLoad;
