// Storage
// =======
// View showing files, snapshots, volumes, and disks. Provides utilities to
// manage storage at all levels, including the creation and deletion of ZFS
// pools / volumes, etc.

"use strict";

import React from "react";

import Pools from "./Storage/Pools";
import Disks from "./Storage/Disks";

const Storage = React.createClass(
  { displayName: "Storage"

  , render: function () {
      return (
        <main>
          <Pools />
          <Disks />
        </main>
      );
    }
  }
);

export default Storage;
