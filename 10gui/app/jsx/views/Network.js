/** @jsx React.DOM */

// Network
// ================
// View showing network information, link state, VLANs, and other entities.

"use strict";


var React  = require("react");
var Viewer = require("../components/Viewer");

// Dummy data from API call on relatively unmolested system
// TODO: Update to use data from Flux store
var inputData  = require("../../fakedata/network-interfaces.json");
var formatData = require("../../middleware-keys/network-interfaces-display.json")[0];

var Network = React.createClass({
  render: function() {
    return (
      <div>
        <h2>Network View</h2>
        <Viewer header     = { "Network Interfaces" }
                inputData  = { inputData }
                formatData = { formatData } >
        </Viewer>
      </div>
    );
  }
});

module.exports = Network;