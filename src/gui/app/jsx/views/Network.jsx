// Network
// =======

"use strict";

var componentLongName = "Networks";

import React from "react";

import { RouteHandler } from "react-router";

import routerShim from "../components/mixins/routerShim";

import SectionNav from "../components/SectionNav";

var sections = [ { route: "network-config"
                 , display: "Network Overview"
                 }
               , { route : "interfaces"
                 , display : "Interfaces"
                 }
               , { display: "LAGGs" }
               , { display: "Routes" }
               , { display: "VLANs" }
               ]

const Network = React.createClass({

  displayName: "Network"

  , mixins: [ routerShim ]

  , componentDidMount: function () {
    this.calculateDefaultRoute( "network", "network-config", "endsWith" );
  }

  , componentWillUpdate: function ( prevProps, prevState ) {
    this.calculateDefaultRoute( "network", "network-config", "endsWith" );
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
