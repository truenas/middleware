// COMMON VIEWER MODE MIXIN
// ========================
// This mixin contains useful methods that apply to cross-cutting concerns in
// the various different viewer modes.

"use strict";

import _ from "lodash";
import React from "react";

const ViewerCommon =

  { contextTypes: { router: React.PropTypes.func }

  , propTypes:
    { keyUnique           : React.PropTypes.string.isRequired
    , keyPrimary          : React.PropTypes.oneOfType(
                              [ React.PropTypes.number
                              , React.PropTypes.string
                              ]
                            )
    , keySecondary        : React.PropTypes.oneOfType(
                              [ React.PropTypes.number
                              , React.PropTypes.string
                              ]
                            )

    , searchKeys          : React.PropTypes.instanceOf( Set )

    , itemData            : React.PropTypes.oneOfType(
                              [ React.PropTypes.object
                              , React.PropTypes.array
                              ]
                            )
    , itemSchema          : React.PropTypes.object.isRequired
    , itemLabels          : React.PropTypes.object.isRequired

    , routeName           : React.PropTypes.string.isRequired
    , routeParam          : React.PropTypes.string.isRequired
    , routeNewItem        : React.PropTypes.string

    , textNewItem         : React.PropTypes.string.isRequired
    , textRemaining       : React.PropTypes.string.isRequired
    , textUngrouped       : React.PropTypes.string.isRequired

    , customDetailNavItem : React.PropTypes.func
    , customIconNavItem   : React.PropTypes.func
    }

  , getRequiredProps: function () {
      return _.pick( this.props
                   , [ "searchString"

                     , "keyUnique"
                     , "keyPrimary"
                     , "keySecondary"

                     , "itemSchema"
                     , "itemLabels"

                     , "routeName"
                     , "routeParam"

                     , "textNewItem"
                     , "textRemaining"
                     , "textUngrouped"
                     ]
                   )
    }

  , addingEntity: function () {
      return _.endsWith( this.context.router.getCurrentPathname()
                       , this.props.routeAdd );
    }

  , dynamicPathIsActive: function () {
      if ( this.context.router.getCurrentParams()[ this.props.routeParam ] ) {
        return true;
      } else {
        return false;
      }
    }

  , returnToViewerRoot: function () {
      if ( this.isMounted() && this.dynamicPathIsActive() ) {
        var currentRoutes = this.context.router.getCurrentRoutes();
        var currentIndex = _.findIndex( currentRoutes, function ( routeData ) {
          return _.contains( routeData["paramNames"], this.props.routeParam );
        }, this );

        this.context.router.transitionTo( currentRoutes[ currentIndex - 1 ]["path"] );
      }
    }

};

export default ViewerCommon;
