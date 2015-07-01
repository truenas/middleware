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
    , handleVdevAdd        : React.PropTypes.func.isRequired
    , handleVdevRemove     : React.PropTypes.func.isRequired
    , handleVdevTypeChange : React.PropTypes.func.isRequired
    , availableDisks       : React.PropTypes.array.isRequired
    , cols                 : React.PropTypes.number
    , children             : React.PropTypes.array
    , status               : React.PropTypes.string
    , path                 : React.PropTypes.string
    , purpose: React.PropTypes.oneOf(
        [ "data"
        , "logs"
        , "cache"
        , "spare"
        ]
      )
    , type: React.PropTypes.oneOf(
        [ "disk"
        // , "file" // FIXME: This will probably never be used.
        , "mirror"
        , "raidz1"
        , "raidz2"
        , "raidz3"
        , "unassigned" // This can only be assigned by "getDefaultProps"
        ]
      )
    // index of the volume of which this vdev is a member
    , volumeKey: React.PropTypes.number.isRequired
    }

  , getDefaultProps: function () {
    return { purpose : "data"
           , cols    : 4
           , type    : "unassigned"
           };
  }

  , getInitialState: function () {
    return { children : this.props.children
           , path     : this.props.path
           , type     : this.props.type
           };
  }

  // FIXME: This function is temporary, and should be removed
  , createNewDiskOptions: function ( disk, index ) {
    return (
      <option
        key   = { index }
        value = { disk }
      >
        { disk }
      </option>
    );
  }

  , registerNewVdev: function () {
    // TODO: This needs to be able to handle init with an array of disks.
    this.setState({ type: "disk" });
  }

  , render: function () {
    let message     = null;
    let addNewDisks = null;
    let memberDisks = null;

    // Each VDEV will always start out "unassigned", unless it is part of a
    // preexisting volume. The decision to display an "unassigned" VDEV is left
    // to the discretion of the Topology wrapper. "Log" and "Cache", for
    // instance, may only ever display one VDEV.

    if ( this.state.type === "unassigned" ) {
      if ( this.props.availableDisks.length ) {
        // TODO: This layout is a crime against nature
        message = (
          <span
            className = "text-center"
            onClick   = { this.registerNewVdev } >
            <h3><Icon glyph="plus" /></h3>
            <h3>{ "Add " + this.props.purpose }</h3>
          </span>
        );
      } else {
        message = (
          <h4 className="text-center text-muted">
            { "No available " + this.props.purpose + " devices." }
          </h4>
        );
      }
    } else {

      if ( this.props.availableDisks.length ) {
        addNewDisks = (
          <select onChange={ this.props.handleDiskAdd }>
            <option>{ "-- SELECT --" }</option>
            { this.props.availableDisks.map( this.createNewDiskOptions ) }
          </select>
        );
      }

      switch ( this.state.type ) {

        case "unassigned":
          break;

        // "Disk" is an unusual case in the sense that it will have no children
        // and "path" will be defined at the top level. Much of the complexity
        // in this component has to do with transitioning back and forth from
        // "disk" to other layouts.

        case "disk":
          memberDisks = (
            <h4>{ this.state.path }</h4>
          );
          break;

        case "mirror":
        case "raidz1":
        case "raidz2":
        case "raidz3":
          memberDisks = this.state.children.map(
            function ( diskVdev, index ) {
              return <h4 key={ index }>{ diskVdev.path }</h4>;
            }
          );
          break;
      }
    }

    return (
      <TWBS.Col xs={ this.props.cols }>
        { message }
        { memberDisks }
        { addNewDisks }
      </TWBS.Col>
    );
  }

  }
);

export default VDEV;
