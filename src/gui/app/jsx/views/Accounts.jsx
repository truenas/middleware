// Users and Groups
// ================
// View showing all users and groups.

"use strict";

var React = require("react");

var Router       = require("react-router");
var RouteHandler = Router.RouteHandler;

var routerShim = require("../components/mixins/routerShim");

var SectionNav = require("../components/SectionNav");

var sections = [{
    route   : "users"
  , display : "Users"
},{
    route   : "groups"
  , display : "Groups"
}];

var Accounts = React.createClass({displayName: "Accounts",

    mixins: [ routerShim ]

  , componentDidMount: function() {
      this.calculateDefaultRoute( "accounts", "users", "endsWith" );
    }

  , componentWillUpdate: function( prevProps, prevState ) {
      this.calculateDefaultRoute( "accounts", "users", "endsWith" );
    }

  , render: function() {
      return (
        <main>
          <SectionNav views = { sections } />
          <RouteHandler />
        </main>
      );
    }
});

module.exports = Accounts;
