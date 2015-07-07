// VDEV
// ====
// A simple wrapper component for representing a single VDEV.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import Icon from "../../../components/Icon";

import VDEVDisk from "./VDEVDisk";

const VDEV = React.createClass(
  { propTypes:
    { handleDiskAdd        : React.PropTypes.func.isRequired
    , handleDiskRemove     : React.PropTypes.func.isRequired
    , handleVdevRemove     : React.PropTypes.func.isRequired
    , handleVdevTypeChange : React.PropTypes.func.isRequired
    , availableDevices     : React.PropTypes.array.isRequired
    , cols                 : React.PropTypes.number
    , children             : React.PropTypes.array
    , status               : React.PropTypes.string
    , path                 : React.PropTypes.string
    , purpose: React.PropTypes.oneOf(
        [ "data"
        , "logs"
        , "cache"
        , "spares"
        ]
      ).isRequired
    , type: React.PropTypes.oneOf(
        [ null // Used for new vdevs. Such a vdev should have a falsy path, no
               // children, and a falsy existsOnServer.
        , "disk"
        // , "file" // FIXME: This will probably never be used.
        , "mirror"
        , "raidz1"
        , "raidz2"
        , "raidz3"
        ]
      ).isRequired
    // index of the volume of which this vdev is a member
    , volumeKey: React.PropTypes.number.isRequired
    // index of this vdev in the array of vdevs of the same purpose
    , vdevKey: React.PropTypes.number.isRequired
    // used to check if this vdev is already known to the server and thus make
    // it immutable.
    , existsOnServer: React.PropTypes.bool
    }

  , getDefaultProps: function () {
    return { purpose : "data"
           , cols    : 4
           };
  }

  // FIXME: This function is temporary, and should be removed
  , createNewDeviceOptions: function ( device, index ) {
    return (
      <option
        key   = { index }
        value = { device }
        label = { device } />
    );
  }

  , render: function () {
    let addNewDisks = null;
    let memberDisks = null;

    switch ( this.props.type ) {

      // "Disk" is an unusual case in the sense that it will have no children
      // and "path" will be defined at the top level. Much of the complexity
      // in this component has to do with transitioning back and forth from
      // "disk" to other layouts.
      case "disk":
        memberDisks = (
          <VDEVDisk
            path             = { this.props.path }
            volumeKey        = { this.props.volumeKey }
            vdevKey          = { this.props.vdevKey }
            vdevPurpose      = { this.props.purpose }
            handleDiskRemove = { this.props.handleDiskRemove }
            existsOnServer   = { this.props.existsOnServer }
            key              = { 0 }
          />
        );
        break;

      case "mirror":
      case "raidz1":
      case "raidz2":
      case "raidz3":
        memberDisks = this.props.children.map(
          function ( diskVdev, index ) {
            return (
              <VDEVDisk
                path             = { diskVdev.path }
                volumeKey        = { this.props.volumeKey }
                vdevKey          = { this.props.vdevKey }
                vdevPurpose      = { this.props.purpose }
                handleDiskRemove = { this.props.handleDiskRemove }
                existsOnServer   = { this.props.existsOnServer }
                key              = { index }
              />
            );
          }.bind( this )
        );
        break;
    }

    // Only make a list of new disks to add if there are any available devices
    // and the vdev is modifiable (doesn't exist on the server already)
    if ( this.props.availableDevices.length && !this.props.existsOnServer ) {
      addNewDisks =
        <select
          // Reset the field to nothing selected every time so that it doesn't
          // move to a valid option and make it impossible to select that one
          // next.
          value = "-- SELECT --"
          onChange= { this.props.handleDiskAdd.bind( null
                                                   , this.props.volumeKey
                                                   , this.props.purpose
                                                   , this.props.vdevKey
                                                   )
                    } >
          <option>{ "-- SELECT --" }</option>
          { this.props.availableDevices.map( this.createNewDeviceOptions ) }
        </select>;
    } else {
      addNewDisks = <h5>{ "There are no more devices available." }</h5>;
    }


    return (
      <TWBS.Col xs={ this.props.cols }>
        { memberDisks }
        { addNewDisks }
      </TWBS.Col>
    );
  }

  }
);

export default VDEV;
