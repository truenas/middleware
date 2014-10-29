/** @jsx React.DOM */

// Users and Groups
// ================
// View showing all users and groups.

"use strict";


var React  = require("react");
var Viewer = require("../components/Viewer");

var displayData = {
    // Dummy data from API call on relatively unmolested system
    // TODO: Update to use data from Flux store
    inputData : require("../../fakedata/accounts.json")
  , primary   : "bsdusr_username"
  , secondary : "bsdusr_full_name"
  , sortBy    : ["bsdusr_builtin"]
};

var Users = React.createClass({
    render: function() {
    return (
      <div>
        <h2>Users View</h2>
        <Viewer header       = { "User Accounts" }
                displayData  = { displayData } >
        </Viewer>
      </div>
    );
  }
});

module.exports = Users;