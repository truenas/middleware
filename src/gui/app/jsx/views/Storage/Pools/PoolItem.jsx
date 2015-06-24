// ZFS POOL / VOLUME ITEM
// ======================
// Individual item which represents a ZFS pool and its associated volume.
// Contains the datasets, ZVOLs, and other high level objects that are
// properties of the pool.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import PoolBreakdown from "./PoolBreakdown";
import VDEV from "./VDEV";

const SLIDE_DURATION = 500;

const PoolItem = React.createClass(
  { displayName: "PoolItem"

  , propTypes:
    { handleDiskAdd  : React.PropTypes.func.isRequired
    , availableDisks : React.PropTypes.array
    , vdevs          : React.PropTypes.array
    , createNew      : React.PropTypes.bool
    }

  , getInitialState: function () {
    return { storageVisible: false
           , topologyVisible: false
           };
  }

  , componentDidUpdate: function ( prevProps, prevState ) {
    if ( prevState["storageVisible"] !== this.state["storageVisible"] ) {
      if ( this.state["storageVisible"] ) {
        Velocity( React.findDOMNode( this.refs.Storage )
                , "slideDown"
                , SLIDE_DURATION
                );
      } else {
        Velocity( React.findDOMNode( this.refs.Storage )
                , "slideUp"
                , SLIDE_DURATION
                );
      }
    }

    if ( prevState["topologyVisible"] !== this.state["topologyVisible"] ) {
      if ( this.state["topologyVisible"] ) {
        Velocity( React.findDOMNode( this.refs.Topology )
                , "slideDown"
                , SLIDE_DURATION
                );
      } else {
        Velocity( React.findDOMNode( this.refs.Topology )
                , "slideUp"
                , SLIDE_DURATION
                );
      }
    }
  }

  , createDiskOptions: function () {
    return (
      this.props.selectedDisks.map( path => <option>{ path }</option> )
    );
  }

  , toggleStorage: function () {
    let newState = { storageVisible: !this.state.storageVisible };

    if ( newState["storageVisible"] ) {
      newState["topologyVisible"] = false;
    }

    this.setState( newState );
  }

  , toggleTopology: function () {
    let newState = { topologyVisible: !this.state.topologyVisible };

    if ( newState["topologyVisible"] ) {
      newState["storageVisible"] = false;
    }

    this.setState( newState );
  }

  , hideBoth: function () {
    this.setState(
      { storageVisible: false
      , topologyVisible: false
      }
    );
  }

  , render: function () {
      let vdevCommon =
        { availableDisks : this.props.availableDisks
        , handleDiskAdd  : this.props.handleDiskAdd
        };

      return (
        <TWBS.Panel>
          <TWBS.Well
            ref   = "Storage"
            style = {{ display: "none" }}
          >
            <h1>Storage goes here, when you have it</h1>
          </TWBS.Well>

          <TWBS.Row>
            <TWBS.Col xs={ 3 }>
              <h3>MyPool</h3>
            </TWBS.Col>
            <TWBS.Col xs={ 3 }>
              <h3>3.0TB</h3>
            </TWBS.Col>
            <TWBS.Col xs={ 4 }>
              <PoolBreakdown
                free   = { 50 }
                used   = { 15 }
                parity = { 35 }
                total  = { 100 }
              />
            </TWBS.Col>
            <TWBS.Col xs={ 2 }>
              <TWBS.Button
                block
                bsStyle = "default"
                onClick = { this.toggleStorage }
              >
                Show Volumes
              </TWBS.Button>
              <TWBS.Button
                block
                bsStyle = "default"
                onClick = { this.toggleTopology }
              >
                Show Topology
              </TWBS.Button>
            </TWBS.Col>
          </TWBS.Row>

          <TWBS.Well
            ref   = "Topology"
            style = {{ display: "none" }}
          >

            <TWBS.Row>
              {/* LOG AND CACHE DEVCES */}
              <TWBS.Col xs={ 6 }>
                <h3>Cache</h3>
                <VDEV { ...vdevCommon }
                  cols = { 12 }
                  type = "cache"
                />
              </TWBS.Col>
              <TWBS.Col xs={ 6 }>
                <h3>Log</h3>
                <VDEV { ...vdevCommon }
                  cols = { 12 }
                  type = "log"
                />
              </TWBS.Col>

              {/* STORAGE VDEVS */}
              <TWBS.Col xs={ 12 }>
                <h3>Storage</h3>
                <VDEV { ...vdevCommon } />
              </TWBS.Col>
            </TWBS.Row>

          </TWBS.Well>

        </TWBS.Panel>
      );
    }
  }
);

export default PoolItem;
