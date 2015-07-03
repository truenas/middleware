// TOPOLOGY DRAWER
// ==============
// A section of the Pool/Volume UI that shows the constituent VDEVs which are
// being used for logs, cache, data, and spares.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import Icon from "../../../components/Icon";

import VDEV from "./VDEV";

var TopologyDrawer = React.createClass(

  { propTypes:
    { handleDiskAdd        : React.PropTypes.func.isRequired
    , handleDiskRemove     : React.PropTypes.func.isRequired
    , handleVdevAdd        : React.PropTypes.func.isRequired
    , handleVdevRemove     : React.PropTypes.func.isRequired
    , handleVdevTypeChange : React.PropTypes.func.isRequired
    , availableDisks       : React.PropTypes.array.isRequired
    , availableSSDs        : React.PropTypes.array.isRequired
    , data                 : React.PropTypes.array.isRequired
    , logs                 : React.PropTypes.array.isRequired
    , cache                : React.PropTypes.array.isRequired
    , spares               : React.PropTypes.array.isRequired
    , volumeKey            : React.PropTypes.number.isRequired
    , volumesOnServer      : React.PropTypes.array.isRequired
    }

  , createVdevs: function ( purpose ) {
    const commonProps =
      { handleDiskAdd        : this.props.handleDiskAdd
      , handleDiskRemove     : this.props.handleDiskRemove
      , handleVdevRemove     : this.props.handleVdevRemove
      , handleVdevTypeChange : this.props.handleVdevTypeChange
      , volumeKey            : this.props.volumeKey
      };
    let availableDevices;
    let cols;
    let newVdevAllowed = false;
    let newVdev = null;
    let vdevs = [];

    switch ( purpose ) {
      case "logs":
      case "cache":
        availableDevices = this.props.availableSSDs;
        cols           = 12;
        // Log and Cache currently only allow a single VDEV.
        if ( this.props[ purpose ].length < 1 ) {
          newVdevAllowed = true;
        }
        break;

      case "spares":
      case "data":
      default:
        availableDevices = this.props.availableDisks;
        cols           = 4;    // TODO: More intricate logic for this
        newVdevAllowed = true; // TODO: There should be cases where we don't
        break;
    }

    vdevs = this.props[ purpose ].map(
      function ( vdev, index ) {
        // Destructure vdev to avoid passing in props which will not be used.
        let { children, status, type, path } = vdev;

        // A vdev exists on the server if the volume it's in does and the
        // volume has a vdev of that purpose and index. This only applies to
        // "data" vdevs.
        let existsOnServer = this.props.volumesOnServer.length
                           < this.props.volumeKey
                          && this.props.volumesOnServer[ this.props.volumeKey ]
                                                       [ "topology" ]
                                                       [ purpose ]
                                                       .length
                           < this.props.vdevKey
                          && this.props.purpose === "data";

        return (
          <VDEV { ...commonProps }
            children          = { children }
            status            = { status }
            type              = { type }
            path              = { path }
            purpose           = { purpose }
            cols              = { cols }
            availableDevices  = { availableDevices }
            volumeKey         = { this.props.volumeKey }
            vdevKey           = { index }
            key               = { index }
            existsOnServer    = { existsOnServer }
          />
        );
      }.bind( this )
    );

    // This condition is used only for policy limiting the number of vdevs of
    // some purpose, for example limiting log and cache vdevs to one.
    if ( !newVdevAllowed ) {
      newVdev =
        <TWBS.Col xs = { cols } >
          <h4 className="text-center text-muted">
            { "No more " + purpose + " may be added." }
          </h4>
        </TWBS.Col>;
    } else if ( availableDevices.length ) {
      newVdev = (
        <TWBS.Col xs = { cols } >
          <span
            className = "text-center"
            onClick   = { this.props.handleVdevAdd.bind( null
                                                       , this.props.volumeKey
                                                       , purpose
                                                       ) } >
            <h3><Icon glyph = "plus" /></h3>
            <h3>{ "Add " + purpose }</h3>
          </span>
        </TWBS.Col>
      );
    } else {
      newVdev = (
        <TWBS.Col xs = { cols } >
          <h4 className="text-center text-muted">
            { "No available " + purpose + " devices." }
          </h4>
        </TWBS.Col>
      );
    }

    vdevs.push( newVdev );

    return vdevs;
  }

  , render: function () {

    return (
      <TWBS.Well
        style = {{ display: "none" }}
      >

        <TWBS.Row>
          {/* LOG AND CACHE DEVCES */}
          <TWBS.Col xs={ 6 }>
            <h4>Cache</h4>
            { this.createVdevs( "cache" ) }
          </TWBS.Col>
          <TWBS.Col xs={ 6 }>
            <h4>Log</h4>
            { this.createVdevs( "logs" ) }
          </TWBS.Col>

          {/* STORAGE VDEVS */}
          <TWBS.Col xs={ 12 }>
            <h4>Storage</h4>
            { this.createVdevs( "data" ) }
          </TWBS.Col>

          {/* SPARE VDEVS */}
          <TWBS.Col xs={ 12 }>
            <h4>Spares</h4>
            { this.createVdevs( "spares" ) }
          </TWBS.Col>
        </TWBS.Row>

      </TWBS.Well>
    );
  }

  }
);

export default TopologyDrawer;
