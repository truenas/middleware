// Contextual Disks Display
// ========================
// A contextual popout for use with the ContextBar component. Displays icons
// for all disks that are not part of a volume so that they may be used for
// new vdev creation.

"use strict";

import React from "react";
import _ from "lodash";

import DiskItemIcon from "../views/Storage/Disks/DiskItemIcon";

const ContextDisks = React.createClass({

  propTypes: { disks: React.PropTypes.object }

  , render: function () {
    return (
      <h4>
        { "Available Disks" }
      </h4>
    );
  }

});

export default ContextDisks;
