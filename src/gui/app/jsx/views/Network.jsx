// Network
// =======

"use strict";

var componentLongName = "Networks";

import React from "react";

import { RouteHandler } from "react-router";

import routerShim from "../components/mixins/routerShim";

import SectionNav from "../components/SectionNav";

var sections = [ { route : "interfaces"
                 , display : "Interfaces"
                 }
               , { route: "network-config"
                 , display: "Network Configuration"
                } ]

var Network = React.createClass({

  displayName: "Network"

  , mixins: [ routerShim ]

  , componentDidMount: function () {
      this.calculateDefaultRoute( "network", "interfaces", "endsWith" );
    }

  , componentWillUpdate: function ( prevProps, prevState ) {
      this.calculateDefaultRoute( "network", "interfaces", "endsWith" );
    }

  , render: function () {
    return (
      <main>
        <SectionNav views = { sections } />
        <RouteHandler />
      </main>
    );
  }

});

export default Network;
