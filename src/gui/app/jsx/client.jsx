// CLIENT ENTRYPOINT
// =================
// Counterpart to ./index.js. client provides interface to the rest of the app,
// and wraps the app's routes component.

"use strict";

var React = require("react");

// Routing
var Router = require("react-router");
var Routes = require("./routes");

// Middleware
var MiddlewareClient = require("./middleware/MiddlewareClient");
var protocol = ( window.location.protocol === "https:" ? "wss://" : "ws://" );

MiddlewareClient.connect( protocol + document.domain + ":5000/socket" );

Router.run( Routes, Router.HistoryLocation, function( Handler, state ) {
  React.render( <Handler />, document.body );
});
