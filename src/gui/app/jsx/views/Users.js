/** @jsx React.DOM */

// Users and Groups
// ================
// View showing all users and groups.

"use strict";


var React  = require("react");
var Viewer = require("../components/Viewer");

// Dummy data from API call on relatively unmolested system
// TODO: Update to use data from Flux store
var inputData  = require("../../data/fakedata/accounts.json");
var formatData = require("../../data/middleware-keys/accounts-display.json")[0];

var Users = React.createClass({
    render: function() {
    return (
      <div>
        <h2>Cool people</h2>
        <Viewer header     = { "User Accounts" }
                inputData  = { inputData }
                formatData = { formatData } >
        </Viewer>
      </div>
    );
  }
});

module.exports = Users;