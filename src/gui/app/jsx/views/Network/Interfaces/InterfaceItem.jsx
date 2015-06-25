// Interface Item
// ==============
// Handles viewing and and changing of network interfaces.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import routerShim from "../../../components/mixins/routerShim";
import clientStatus from "../../../components/mixins/clientStatus";
import viewerCommon from "../../../components/mixins/viewerCommon";

import IS from "../../../stores/InterfacesStore";
import IM from "../../../middleware/InterfacesMiddleware"

import InterfaceView from "./InterfaceView"
import InterfaceEdit from "./InterfaceEdit";

const InterfaceItem = React.createClass(
  { mixins: [ routerShim, clientStatus, viewerCommon ]

  , getInitialState: function () {
      return {
        targetInterface: this.getInterfaceFromStore()
        , currentMode: "view"
        , activeRoute: this.getDynamicRoute()
      };
    }

  , componentDidUpdate: function ( prevProps, prevState ) {
      var activeRoute = this.getDynamicRoute();

      if ( activeRoute !== prevState.activeRoute ) {
        this.setState({
          targetInterface: this.getInterfaceFromStore()
          , currentMode: "view"
          , activeRoute: activeRoute
        });
      }
    }

  , componentDidMount: function () {
      IS.addChangeListener( this.updateInterfaceInState );
    }

  , componentWillUnmount: function () {
      IS.removeChangeListener( this.updateInterfaceInState );
    }

  , getInterfaceFromStore: function () {
      return IS.findInterfaceByKeyValue( this.props.keyUnique
                                       , this.getDynamicRoute() );
    }

  , updateInterfaceInState: function () {
      this.setState({ targetInterface: this.getInterfaceFromStore() });
    }

  , downInterface: function () {
    IM.downInterface( this.state.targetInterface.name );
  }

  , upInterface: function () {
    IM.upInterface( this.state.targetInterface.name );
  }

  , handleViewChange: function ( nextMode, event ) {
      this.setState({ currentMode: nextMode });
    }

  , render: function () {
    var DisplayComponent = null;

    if ( this.state.SESSION_AUTHENTICATED && this.state.targetInterface ) {
      var childProps = {
        handleViewChange  : this.handleViewChange
        , item            : this.state.targetInterface
        , upInterface     : this.upInterface
        , downInterface   : this.downInterface
      };

      switch ( this.state.currentMode ) {
        default:
        case "view":
          DisplayComponent =
            <InterfaceView { ...this.getRequiredProps() } {...childProps} />;
          break;
        case "edit":
          DisplayComponent =
            <InterfaceEdit { ...this.getRequiredProps() } {...childProps} />;
          break;
      }
    }

    return (
      <div className="viewer-item-info">

      { DisplayComponent }

    </div>
    );
  }

});

export default InterfaceItem;
