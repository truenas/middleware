// ACTIVE ROUTE MIXIN
// ==================
// Helper mixin designed to return the active path to Viewers already using the
// Router.State mixin

"use strict";

module.exports = {
    getActiveRoute: function() {
      return this.getParams()[ this.props.viewData.routing["param"] ];
    }
};
