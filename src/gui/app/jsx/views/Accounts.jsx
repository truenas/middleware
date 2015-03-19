// Users and Groups
// ================
// View showing all users and groups.

"use strict";


var React = require("react");

var Router       = require("react-router");
var RouteHandler = Router.RouteHandler;

var SectionNav = require("../components/SectionNav");

var sections = [{
    route   : "users"
  , display : "Users"
},{
    route   : "groups"
  , display : "Groups"
}];

var Accounts = React.createClass({

    render: function() {
      return (
        <main>
          <SectionNav views = { sections } />
          <RouteHandler />
        </main>
      );
    }
});

module.exports = Accounts;
