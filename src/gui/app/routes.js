/** @jsx React.DOM */

// FREENAS GUI ROUTES
"use strict";


var Router       = require("react-router");
var Routes       = Router.Routes;
var Route        = Router.Route;
var DefaultRoute = Router.DefaultRoute;

module.exports = (
  <Routes location="history">
    <Route name="root" path="/" handler={ require("./jsx/views/FreeNASWebApp") }>
      <Route name="dashboard" handler={ require("./jsx/views/Dashboard") } />
      <Route name="storage" handler={ require("./jsx/views/Storage") } />
      <Route name="tasks" handler={ require("./jsx/views/Tasks") } />
      <Route name="users" handler={ require("./jsx/views/Users") } />
      <Route name="control-panel" handler={ require("./jsx/views/ControlPanel") } />
      <Route name="network" handler={ require("./jsx/views/Network") } />
      <DefaultRoute handler={ require("./jsx/views/Dashboard") } />
    </Route>
  </Routes>
);