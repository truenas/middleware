// ROUTER SHIM
// ===========
// Helper mixins designed to shim react-router with some helpful functionality.
// Offers simple getter and redirect methods based on simple, semantic
// expressions.

"use strict";

import _ from "lodash";
import React from "react";

module.exports = {

    contextTypes: {
      router: React.PropTypes.func
    }

  , routeEndsWith: function( route ) {
      var rc = this.context.router;

      return _.endsWith( rc.getCurrentPathname(), route );
    }

  , routeIs: function( route ) {
      var rc = this.context.router;

      return rc.getCurrentPathname() === route;
    }

  , calculateDefaultRoute: function( testRoute, target, testType ) {
      var rc         = this.context.router;
      var testString = testType.toLowerCase();
      var shouldRedirect;

      switch( testString ) {
        case "routeis":
        case "is":
          shouldRedirect = this.routeIs( testRoute );
          break;

        case "routeendswith":
        case "endswith":
          shouldRedirect = this.routeEndsWith( testRoute );
          break;

        default:
          shouldRedirect = this.routeEndsWith( testRoute );
          break;
      }

      if ( shouldRedirect ) {
        rc.replaceWith( target );
      }
    }

  , getDynamicRoute: function () {
      var rc = this.context.router;

      return rc.getCurrentParams()[ this.props.viewData.routing["param"] ];
    }

};
