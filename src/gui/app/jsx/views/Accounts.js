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
        <div>
          <SectionNav views = { sections } />
          { this.props.activeRouteHandler() }
        </div>
      );
    }
});

module.exports = Accounts;