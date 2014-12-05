/** @jsx React.DOM */

// CLIENT ROUTER AND MOUNTPOINT
"use strict";

require("./ENV");

// React
var React      = require("react");

var routes     = require("./routes");
var mountpoint = document.body;

// Middleware
var MiddlewareClient = require("./jsx/middleware/MiddlewareClient");
var protocol = ( window.location.protocol === "https:" ? "wss://" : "ws://" );

// Begin Middleware connection before rendering React components
MiddlewareClient.connect( protocol + document.domain + ":5000/socket" );

// Render Routes into document body
React.renderComponent( routes, mountpoint, function() {
  window.ROUTER_PROPS = {};
});