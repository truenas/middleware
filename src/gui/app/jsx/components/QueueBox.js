/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("./Icon");

var QueueBox = React.createClass({
  getDefaultProps: function() {
    return {
      isVisible: 0
    };
  },
  render: function() {
    return (      
      <div className={"notifyBoxes queueBox "  + ((this.props.isVisible) ? "visible" : "hidden") }>
      Queue! Queue!
      </div>
    );
  }
});

module.exports = QueueBox;