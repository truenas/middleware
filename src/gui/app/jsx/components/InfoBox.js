/** @jsx React.DOM */

"use strict";

var React = require("react");

var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("./Icon");

var InfoBox = React.createClass({
  render: function() {
    return (
      <div className="xnotifyBoxes infoBox">
      Info! Info!
      </div>
    );
  }
});

module.exports = InfoBox;