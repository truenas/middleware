/** @jsx React.DOM */

// Groups
// ======
// Viewer for FreeNAS groups.

"use strict";


var React    = require("react");

var Viewer   = require("../../components/Viewer");

// Dummy data from API call on relatively unmolested system
// TODO: Update to use data from Flux store
var inputData  = require("../../../data/fakedata/accounts.json");
var formatData = require("../../../data/middleware-keys/accounts-display.json")[0];

var Groups = React.createClass({
    render: function() {
      return (
        <Viewer header     = { "Groups" }
                inputData  = { inputData }
                formatData = { formatData }
                Editor     = { this.props.activeRouteHandler } >
        </Viewer>
      );
    }
});

module.exports = Groups;
