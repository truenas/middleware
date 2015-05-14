// COMMON VIEWER MODE MIXIN
// ========================
// This mixin contains useful methods that apply to cross-cutting concerns in
// the various different viewer modes.

"use strict";

import _ from "lodash";

module.exports = {

    addingEntity: function () {
      if ( _.endsWith( this.context.router.getCurrentPathname(), this.props.viewData.routing.addentity ) ) {
        return true;
      } else {
        return false;
      }

    }

  , dynamicPathIsActive: function () {
      if ( this.context.router.getCurrentParams()[ this.props.viewData.routing.param ] ) {
        return true;
      } else {
        return false;
      }
    }

  , returnToViewerRoot: function () {
      if ( this.isMounted() && this.dynamicPathIsActive() ) {
        var currentRoutes = this.context.router.getCurrentRoutes();
        var currentIndex = _.findIndex( currentRoutes, function( routeData ) {
          return _.contains( routeData["paramNames"], this.props.viewData.routing.param );
        }, this );

        this.context.router.transitionTo( currentRoutes[ currentIndex - 1 ]["path"] );
      }
    }

  , tryPathChange: function () {
      if ( true ) {

      } else {
        console.log("couldn't do the thing");
        this.returnToViewerRoot();
      }
    }

};
