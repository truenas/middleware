// VDEV
// ====
// A simple wrapper component for representing a single VDEV.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import Icon from "../../../components/Icon";

const VDEV = React.createClass(
  { propTypes:
    { handleDiskAdd  : React.PropTypes.func.isRequired
    , availableDisks : React.PropTypes.array.isRequired
    , cols           : React.PropTypes.number
    , children       : React.PropTypes.array
    , status         : React.PropTypes.string
    , path           : React.PropTypes.string
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

  , render: function () {
    let contents = null;

    switch ( this.state.type ) {

// Each VDEV will always start out "unassigned", unless it is part of a
// preexisting volume. The decision to display an "unassigned" VDEV is left to
// the discretion of the Topology wrapper. "Log" and "Cache", for instance, may
// only ever display one VDEV.

      case "unassigned":
        if ( this.props.availableDisks.length ) {
          // TODO: This layout is a crime against nature
          contents = (
            <span className="text-center">
              <h3><Icon glyph="plus" /></h3>
              <h3>{ "Add " + this.props.purpose }</h3>
            </span>
          );
        } else {
          contents = (
            <h4 className="text-center text-muted">
              { "No available " + this.props.purpose + " devices." }
            </h4>
          );
        }
        break;

// "Disk" is an unusual case in the sense that it will have no children and
// "path" will be defined at the top level. Much of the complexity in this
// component has to do with transitioning back and forth from "disk" to other
// layouts.

      case "disk":
        contents = (
          <h4>{ this.state.path }</h4>
        );
        break;

      case "mirror":
      case "raidz1":
      case "raidz2":
      case "raidz3":
        contents = this.state.children.map(
          function ( diskVdev, index ) {
            return <h4 key={ index }>{ diskVdev.path }</h4>;
          }
        );
        break;
    }

    return (
      <TWBS.Col xs={ this.props.cols }>
        { contents }
      </TWBS.Col>
    );
  }

  }
);

export default VDEV;
