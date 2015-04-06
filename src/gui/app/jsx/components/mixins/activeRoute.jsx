// ACTIVE ROUTE MIXIN
// ==================
// Helper mixin designed to return the active path to Viewers already using the
// Router.State mixin

"use strict";

var React = require("react");

module.exports = {

    contextTypes: {
      router: React.PropTypes.func
    }

  , getActiveRoute: function() {
      return this.context.router.getCurrentParams()[ this.props.viewData.routing["param"] ];
    }
};
