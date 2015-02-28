// Groups
// ======
// Viewer for FreeNAS groups.

"use strict";


var React = require("react");

var Router       = require("react-router");
var RouteHandler = Router.RouteHandler;

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
                Editor     = { RouteHandler } >
        </Viewer>
      );
    }
});

module.exports = Groups;
