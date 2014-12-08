/** @jsx React.DOM */

// Groups
// ======
// Viewer for FreeNAS groups.

"use strict";


var React  = require("react");
var Viewer = require("../../components/Viewer");

var formatData = require("../../../data/middleware-keys/accounts-display.json")[0];
var itemData = {
    "route" : "users-editor"
  , "param" : "userID"
};

var Groups = React.createClass({
    render: function() {
      return (
        <Viewer header     = { "Groups" }
                inputData  = { inputData }
                formatData = { formatData }
                itemData   = { itemData }
                Editor     = { this.props.activeRouteHandler } >
        </Viewer>
      );
    }
});

module.exports = Groups;
