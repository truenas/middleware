// ROUTER SHIM
// ===========
// Helper mixins designed to shim react-router with some helpful functionality.
// Offers simple getter and redirect methods based on simple, semantic
// expressions.

"use strict";

var React = require("react");

module.exports = {

    contextTypes: {
      router: React.PropTypes.func
    }

  , getDynamicRoute: function() {
      return this.context.router.getCurrentParams()[ this.props.viewData.routing["param"] ];
    }

};
