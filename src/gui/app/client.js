/** @jsx React.DOM */

// CLIENT ROUTER AND MOUNTPOINT
"use strict";

require("./ENV");

// React
var React      = require("react");

var routes     = require("./routes");
var mountpoint = document.body;

var Middleware = require("./jsx/middleware/middleware");
var protocol = ( window.location.protocol === "https:" ? "wss://" : "ws://" );

Middleware.connect( protocol + document.domain + ":5000/socket" );

Middleware.on("connected", function() {
    var username = prompt("Username:");
    var password = prompt("Password:");
    Middleware.login(username, password);
  }
);

Middleware.on("login", function() {
  React.renderComponent( routes, mountpoint, function() {
    window.ROUTER_PROPS = {};
  });
});