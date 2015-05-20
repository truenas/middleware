// Storage
// =======
// View showing files, snapshots, volumes, and disks. Provides utilities to
// manage storage at all levels, including the creation and deletion of ZFS
// pools / volumes, etc.

"use strict";

import React from "react";

import { RouteHandler } from "react-router";

import routerShim from "../components/mixins/routerShim";

import SectionNav from "../components/SectionNav";

const sections = [ { route: null
                   , display: "Files"
                   , disabled: true
                   }
                 , { route: null
                   , display: "Snapshots"
                   , disabled: true
                   }
                 , { route: "null"
                   , display: "Volumes"
                   , disabled: true
                   }
                 , { route: "disks"
                   , display: "Disks"
                   }
                 ];

const Storage = React.createClass(
  { displayName: "Storage"

  , mixins: [ routerShim ]

  , render: function () {
      return (
        <main>
          <SectionNav views = { sections } />
          <RouteHandler />
        </main>
      );
    }
  }
);

export default Storage;
