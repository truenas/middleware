/** @jsx React.DOM */

// Users
// =====
// Viewer for FreeNAS user accounts and built-in system users.

"use strict";


var React    = require("react");

var Viewer   = require("../../components/Viewer");

// Dummy data from API call on relatively unmolested system
// TODO: Update to use data from Flux store
var inputData  = require("../../../data/fakedata/accounts.json");
var formatData = require("../../../data/middleware-keys/accounts-display.json")[0];

var Users = React.createClass({
    render: function() {
      return (
        <Viewer header     = { "Users" }
                inputData  = { inputData }
                formatData = { formatData } >
        </Viewer>
      );
    }
});

module.exports = Users;
