/** @jsx React.DOM */

// Users and Groups
// ================
// View showing all users and groups.

"use strict";


var React = require("react");

var SectionNav = require("../components/SectionNav");

var sections = [{
    route   : "users"
  , display : "Accounts"
},{
    route   : "groups"
  , display : "Groups"
}];

var Accounts = React.createClass({
    render: function() {
      return (
        <main>
          <SectionNav views = { sections } />
          { this.props.activeRouteHandler() }
        </main>
      );
    }
});

module.exports = Accounts;