/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("./Icon");

var QueueBox = React.createClass({
  render: function() {
    return (
      <div className="xnotifyBoxes queueBox">
      Queue! Queue!
      </div>
    );
  }
});

module.exports = QueueBox;