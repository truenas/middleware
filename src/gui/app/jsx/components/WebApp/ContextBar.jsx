// Context Bar
// ===============
// Part of the main webapp's window chrome. Positioned on the right side of the
// page, this bar shows user-customizable content including graphs, logged in
// users, and other widgets.

"use strict";


import React from "react";
import _ from "lodash";
import TWBS from "react-bootstrap";

import ContextDisks from "../../context/ContextDisks";


const ContextBar = React.createClass({

  contextTypes: { router: React.PropTypes.func }

  , getInitialState: function () {
    return ( { activeComponent: null
             , lastComponent: null } );
  }

  , popout: function () {
    if ( this.state.activeComponent ) {
      this.setState( { activeComponent: null } );
    } else {
      this.setState( { activeComponent: ContextDisks } );
    }
  }

  , render: function () {

    let popoutButton = null;
    let displaySection = null;
    let DisplayComponent = null;
    let asideClass = "app-sidebar";

    if ( _.endsWith( this.context.router.getCurrentPathname()
                   , "storage" ) ) {
      popoutButton = (
      <TWBS.Button
        onClick = { this.popout } >
        { "Show Disks" }
      </TWBS.Button>
      );
    }

    if ( this.state.activeComponent ) {
      DisplayComponent = this.state.activeComponent;
      asideClass = asideClass + " context-bar-active";
      displaySection = (
        <DisplayComponent />
      );
    } else {
      asideClass = asideClass + " context-bar-inactive";
    }

    return (
      <aside className = { asideClass } >
        <TWBS.Grid>
          <TWBS.Row>
            <TWBS.Col xs = { 12 } >
              { popoutButton }
            </TWBS.Col>
          </TWBS.Row>
          <TWBS.Row>
            <TWBS.Col xs = { 12 } >
              { displaySection }
            </TWBS.Col>
          </TWBS.Row>
        </TWBS.Grid>
      </aside>
    );
  }
});

export default ContextBar;
