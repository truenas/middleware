// VDEVDisk
// ========
// Component for displaying a disk that is a member of an existing or
// in-progress VDEV. In ZFS terms, used to display a special case of the "disk"
// VDEV type where the disk is a child of a VDEV, NOT of a pool topology.

import React from "react";
import TWBS from "react-bootstrap";

const VDEVDisk = React.createClass(
{ propTypes: { serial: React.PropTypes.string
             , byteSize: React.PropTypes.number
             , humanSize: React.PropTypes.string
             , online: React.PropTypes.bool
             , path: React.PropTypes.string.isRequired
             , size: React.PropTypes.number
             , fontSize: React.PropTypes.number
             , badgeFontSize: React.PropTypes.number
             , diskType: React.PropTypes.string
             }

  , render: function () {
    return null;
  }

});

export default VDEVDisk;
