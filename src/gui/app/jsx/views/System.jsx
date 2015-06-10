// System
// =======
//

"use strict";

import React from "react";

import { RouteHandler } from "react-router";

import routerShim from "../components/mixins/routerShim";

import SectionNav from "../components/SectionNav";

const sections = [ { route: "update"
                   , display: "Update"
                   , disabled: false
                   }
                 , { route: "power"
                   , display: "Power"
                   , disabled: false
                   }
                 ];

const System = React.createClass({
  displayName: "System"

  , mixins: [ routerShim ]

  , render: function () {
    return (
      <main>
        <SectionNav views = { sections } />
        <RouteHandler />
      </main>
    );
  }
});

export default System;
