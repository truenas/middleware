// Context Bar
// ===============
// Part of the main webapp's window chrome. Positioned on the right side of the
// page, this bar shows user-customizable content including graphs, logged in
// users, and other widgets.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import EventBus from "../EventBus";

const ContextBar = React.createClass(

  { displayName: "Context Sidebar"

  , componentWillMount: function () {
    EventBus.on( "showContextPanel", this.showContext );
    EventBus.on( "hideContextPanel", this.hideContext );
  }

  , componentWillUnmount: function () {
    EventBus.removeListener( "showContextPanel", this.showContext );
    EventBus.removeListener( "hideContextPanel", this.hideContext );
  }

  , getInitialState: function () {
    return { activeComponent : null
           , lastComponent   : null
           };
  }

  , showContext: function ( reactElement ) {
    if ( reactElement.displayName ) {
      this.setState(
        { activeComponent : reactElement
        , lastComponent   : this.state.activeComponent
        }
      );
    } else {
      console.warn( "Invalid React element passed to " + this.displayName );
      console.dir( reactElement );
    }
  }

  , hideContext: function ( reactElement ) {

    if ( this.state.activeComponent.displayName === reactElement.displayName ) {
      this.setState(
        { activeComponent : this.state.lastComponent
        , lastComponent   : null
        }
      );
    }
  }

  , render: function () {
    let activeComponent = null;

    if ( this.state.activeComponent ) {
      activeComponent = <this.state.activeComponent />;
    }

    return (
      <aside
        className = { "app-sidebar" + this.state.activeComponent
                                    ? " context-bar-active"
                                    : " context-bar-inactive"
                    }
      >
        { activeComponent }
      </aside>
    );
  }
});

export default ContextBar;
