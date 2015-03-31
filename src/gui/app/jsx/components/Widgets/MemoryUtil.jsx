"use strict";

var React = require("react");

var Widget             = require("../Widget");
var DummyWidgetContent = require("./DummyWidgetContent");

var SystemMiddleware = require("../../middleware/SystemMiddleware");
var SystemStore      = require("../../stores/SystemStore");

var statdResources = [
    {
        variable    : "wiredData"
      , dataSource  : "localhost.memory.memory-wired.value"
      , name        : "Wired Memory"
      , color       : "#f39400"
    }
  , {
        variable    : "cacheData"
      , dataSource  : "localhost.memory.memory-cache.value"
      , name        : "Cached Memory"
      , color       : "#8ac007"
    }
  , {
        variable    : "activeData"
      , dataSource  : "localhost.memory.memory-active.value"
      , name        : "Active Memory"
      , color       : "#c9d200"
    }
  , {
        variable    : "freeData"
      , dataSource  : "localhost.memory.memory-free.value"
      , name        : "Free Memory"
      , color       : "#5186ab"
    }
  , {
        variable    : "inactiveData"
      , dataSource  : "localhost.memory.memory-inactive.value"
      , name        : "Inactive Memory"
      , color       : "#b6d5e9"
    }
];

var MemoryUtil = React.createClass({

    getInitialState: function() {
      return { hardware: SystemStore.getSystemInfo( "hardware" ) };
    }

  , componentDidMount: function() {
      SystemStore.addChangeListener( this.handleChange );

      SystemMiddleware.requestSystemInfo( "hardware" );
    }

  , componentWillUnmount: function() {
      SystemStore.removeChangeListener( this.handleChange );
    }

  , primaryChart: function( type ) {
      if ( this.props.primary === undefined && type === "line" ) {
        return true;
      } else if ( type === this.props.primary) {
        return true;
      } else {
        return false;
      }
    }

  , handleChange: function() {
      this.setState({ hardware: SystemStore.getSystemInfo( "hardware" ) });
    }

  , render: function() {

      var chartTypes = [
            {
                type    : "stacked"
              , primary : this.primaryChart("stacked")
              , y: function(d) {
                  if ( d === undefined ) {
                    return 0;
                  } else if ( d[1] === "nan" ) {
                    return null;
                  } else {
                    return Math.round( ( ( ( d[1]/1024 )/1024 ) * 100 ) / 100 ); }
                  }
            }
          , {
                type    : "line"
              , primary : this.primaryChart("line")
              , forceY  : [0, 100]
              , yUnit   : "%"
              , y: function(d) {
                  if( d[1] === "nan" ) {
                    return null;
                  } else {
                    return Math.round( ( ( ( d[1] / this.state.hardware["memory-size"] )*100 )*100 )/100 );
                  }
                }.bind( this )
            }
          , {
                type   : "pie"
              , primary: this.primaryChart("pie")
            }
        ];

      return (
        <Widget
          positionX = { this.props.positionX }
          positionY = { this.props.positionY }
          title     = { this.props.title }
          size      = { this.props.size } >

          <DummyWidgetContent
            statdResources = { statdResources }
            chartTypes     = { chartTypes } >
          </DummyWidgetContent>

        </Widget>
      );
    }

});

module.exports = MemoryUtil;
