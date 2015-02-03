/** @jsx React.DOM */

"use strict";

var React   =   require("react");
var moment  =   require("moment");

var Widget  = 	require("../Widget");

var StatdMiddleware = require("../../middleware/StatdMiddleware");
var StatdStore      = require("../../stores/StatdStore");

function getWidgetDataFromStore() {
 return {
 widgetData: StatdStore.getWidgetData()
  };
 }

var DummyWidgetContent = React.createClass({
  getInitialState: function() {
    return getWidgetDataFromStore();
  }

 , componentDidMount: function() {
    this.requestWidgetData();

    StatdStore.addChangeListener( this.handleStatdChange );
    StatdMiddleware.subscribe();
    console.log(this.state.widgetData);
 }

  , componentWillUnmount: function() {
     StatdStore.removeChangeListener( this.handleStatdChange );
     StatdMiddleware.unsubscribe();
  }

 , handleStatdChange: function() {
    this.setState( getWidgetDataFromStore() );
    console.log(this.state.widgetData);
 }

 , requestWidgetData: function() {
    var stop = moment();
    var start = moment().subtract(15, "m");

    console.log(start.format());
    console.log(stop.format());
    StatdMiddleware.requestWidgetData( "localhost.memory.memory-wired.value", start.format(),  stop.format(), "10S");
  },

  render: function() {
    console.log(this.state.widgetData);
    var elementStyle = {
      margin: "0px",
      padding: "0px"
    };
    return (
      <Widget
    	   positionX  =  {this.props.positionX}
    	   positionY  =  {this.props.positionY}
    	   title      =  {this.props.title}
    	   size       =  {this.props.size} >

        <h3 style={elementStyle}>{"It works!"}</h3>
        <span>{this.state.widgetData}</span>
      </Widget>
    );
  }
});


module.exports = DummyWidgetContent;