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
             , volumeKey: React.PropTypes.number
             , vdevKey: React.PropTypes.number
             , vdevPurpose: React.PropTypes.oneOf(
                [ "data"
                , "logs"
                , "cache"
                , "spares"
                ]
              )
             , handleDiskRemove : React.PropTypes.func
             , existsOnServer   : React.PropTypes.bool
             }

  , render: function () {

    let deleteButton = null;

    if ( this.props.handleDiskRemove
      && this.props.volumeKey > -1
      && this.props.vdevKey > -1
      && !this.props.existsOnServer
       ) {
      deleteButton =
        <TWBS.Button
          bsStyle = "warning"
          onClick = { this.props.handleDiskRemove.bind( null
                                                      , this.props.volumeKey
                                                      , this.props.vdevPurpose
                                                      , this.props.vdevKey
                                                      , this.props.path
                                                      )
                    }
        >
          { "Remove Disk "}
        </TWBS.Button>;
    }

    return (
      <div>
        <TWBS.Label
          bsStyle = "default"
        >
          { this.props.path }
        </TWBS.Label>
        { deleteButton }
      </div>
    );
  }

});

export default VDEVDisk;
