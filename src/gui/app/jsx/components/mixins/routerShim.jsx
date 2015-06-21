// ROUTER SHIM
// ===========
// Helper mixins designed to shim react-router with some helpful functionality.
// Offers simple getter and redirect methods based on simple, semantic
// expressions.

"use strict";

import _ from "lodash";
import React from "react";

const RouterShim =

  { contextTypes: { router: React.PropTypes.func }

  , routeEndsWith: function ( route ) {
      return _.endsWith( this.context.router.getCurrentPathname()
                       , route
                       );
    }

  , routeIs: function ( route ) {
      return this.context.router.getCurrentPathname() === route;
    }

  , calculateDefaultRoute: function ( testRoute, target, testType ) {
      var testString = testType.toLowerCase();
      var shouldRedirect;

      switch ( testString ) {
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
        this.context.router.replaceWith( target );
      }
    }

  , getDynamicRoute: function () {
      return this.context.router.getCurrentParams()[ this.props.routeParam ];
    }

};

export default RouterShim;
