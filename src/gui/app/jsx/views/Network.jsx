// Network
// =======

"use strict";

var componentLongName = "Networks";

import React from "react";

import { RouteHandler } from "react-router";

import routerShim from "../components/mixins/routerShim";

import SectionNav from "../components/SectionNav";

var sections = [ { route: "overview"
                 , display: "Overview"
                 }
               , { route : "interfaces"
                 , display : "Interfaces"
                 }
               , { display: "LAGGs" }
               , { display: "Routes" }
               , { display: "VLANs" }
               , { route   : "network-settings"
                 , display : "Settings"
                 }
               ];

const Network = React.createClass({

  displayName: "Network"

  , mixins: [ routerShim ]

  , componentDidMount: function () {
    this.calculateDefaultRoute( "network", "overview", "endsWith" );
  }

  , componentWillUpdate: function ( prevProps, prevState ) {
    this.calculateDefaultRoute( "network", "overview", "endsWith" );
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
