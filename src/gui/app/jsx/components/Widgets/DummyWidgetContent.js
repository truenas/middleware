/** @jsx React.DOM */

"use strict";

var React   =   require("react");

var Widget  = 	require("../Widget");

var WidgetMiddleware = require("../../middleware/WidgetMiddleware");
var WidgetStore      = require("../../stores/WidgetStore");

function getWidgetDataFromStore() {
 return {
 widgetData: WidgetStore.getWidgetData()
  };
 }

var DummyWidgetContent = React.createClass({
  getInitialState: function() {
    return getWidgetDataFromStore();
  }

 , componentDidMount: function() {
    this.requestWidgetData();

    WidgetStore.addChangeListener( this.handleServicesChange );
 }

  , componentWillUnmount: function() {
     WidgetStore.removeChangeListener( this.handleServicesChange );
  }

 , handleServicesChange: function() {
    this.setState( getWidgetDataFromStore() );
 },

  requestWidgetData: function() {
    WidgetMiddleware.requestWidgetData( "localhost.memory.memory-wired.value", "2015-01-30T13:04:44Z",  "2015-01-30T14:06:44Z", "10S");
  },

  render: function() {
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
      </Widget>
    );
  }
});


module.exports = DummyWidgetContent;