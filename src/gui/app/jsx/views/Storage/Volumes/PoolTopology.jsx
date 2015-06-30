// TOPOLOGY DRAWER
// ==============
// A section of the Pool/Volume UI that shows the constituent VDEVs which are
// being used for logs, cache, data, and spares.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import VDEV from "./VDEV";

var TopologyDrawer = React.createClass(

  { propTypes:
    { handleDiskAdd  : React.PropTypes.func.isRequired
    , availableDisks : React.PropTypes.array.isRequired
    , availableSSDs  : React.PropTypes.array.isRequired
    , data           : React.PropTypes.array.isRequired
    , logs           : React.PropTypes.array.isRequired
    , cache          : React.PropTypes.array.isRequired
    , spare          : React.PropTypes.array.isRequired
    }

  , createVdevs: function ( purpose ) {
    const commonProps = { handleDiskAdd: this.props.handleDiskAdd };
    let availableDisks;
    let cols;
    let newVdevAllowed = false;

    switch ( purpose ) {
      case "logs":
      case "cache":
        availableDisks = this.props.availableSSDs;
        cols           = 12;
        // Log and Cache currently only allow a single VDEV.
        if ( this.props[ purpose ].length < 1 ) {
          newVdevAllowed = true;
        }
        break;

      default:
        availableDisks = this.props.availableDisks;
        cols           = 4;    // TODO: More intricate logic for this
        newVdevAllowed = true; // TODO: There should be cases where we don't
        break;
    }

    let vdevs = this.props[ purpose ].map(
      function ( vdev, index ) {
        // Destructure vdev to avoid passing in props which will not be used.
        let { children, status, type, path } = vdev;

        // The index of the new VDEV item will always be zero, so we start
        // keying here at "1"
        return (
          <VDEV { ...commonProps }
            children       = { children }
            status         = { status }
            type           = { type }
            path           = { path }
            purpose        = { purpose }
            cols           = { cols }
            availableDisks = { availableDisks }
            key            = { index + 1 }
          />
        );
      }
    );

    if ( newVdevAllowed ) {
      vdevs.push(
        <VDEV { ...commonProps }
          purpose        = { purpose }
          cols           = { cols }
          availableDisks = { availableDisks }
          key            = { 0 }
        />
      );
    }

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
            { this.createVdevs( "spare" ) }
          </TWBS.Col>
        </TWBS.Row>

      </TWBS.Well>
    );
  }

  }
);

export default TopologyDrawer;
