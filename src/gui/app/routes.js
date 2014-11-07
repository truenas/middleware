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
      <Route name="accounts" handler={ require("./jsx/views/Accounts") } />
      <Route name="tasks" handler={ require("./jsx/views/Tasks") } />
      <Route name="network" handler={ require("./jsx/views/Network") } />      
      <Route name="storage" handler={ require("./jsx/views/Storage") } />
      <Route name="sharing" handler={ require("./jsx/views/Sharing") } />
      <Route name="services" handler={ require("./jsx/views/Services") } />    
      <Route name="system-tools" handler={ require("./jsx/views/SystemTools") } />
      <Route name="control-panel" handler={ require("./jsx/views/ControlPanel") } />
      <Route name="power" handler={ require("./jsx/views/Power") } />             
      <DefaultRoute handler={ require("./jsx/views/Dashboard") } />
    </Route>
  </Routes>
);