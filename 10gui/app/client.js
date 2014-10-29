/** @jsx React.DOM */

// CLIENT ROUTER AND MOUNTPOINT
"use strict";

require("./ENV");

// React
var React      = require("react");
var routes     = require("./routes");
var mountpoint = document.body;

React.renderComponent( routes, mountpoint, function() {
  window.ROUTER_PROPS = {};
});