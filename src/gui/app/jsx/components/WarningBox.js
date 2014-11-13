/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("./Icon");

var WarningBox = React.createClass({
  getDefaultProps: function() {
    return {
      boxState: "hidden"
    };
  },

  render: function() {
    return (      
      <div className={"notifyBoxes warningBox "  + this.props.boxState}>
      Warning warning!
      </div>
    );
  }
});

module.exports = WarningBox;