/** @jsx React.DOM */

"use strict";

var React   =   require("react");

var Widget  = 	require("../Widget");

var DummyWidgetContent = React.createClass({
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