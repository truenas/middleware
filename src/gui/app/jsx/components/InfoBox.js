/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("./Icon");

var InfoBox = React.createClass({
  getDefaultProps: function() {
    return {
      isVisible: 0
    };
  },
  render: function() {
  	//console.log(this.props.isVisible);
    return (
        <div className={"notifyBoxes infoBox "  + ((this.props.isVisible) ? "visible" : "hidden") }>
      Info! Info!
      </div>
    );
  }
});

module.exports = InfoBox;	