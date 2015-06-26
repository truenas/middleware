// ZFS POOL / VOLUME ITEM
// ======================
// Individual item which represents a ZFS pool and its associated volume.
// Contains the datasets, ZVOLs, and other high level objects that are
// properties of the pool.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import Icon from "../../../components/Icon";
import PoolBreakdown from "./PoolBreakdown";
import StorageDrawer from "./StorageDrawer";
import TopologyDrawer from "./TopologyDrawer";

const SLIDE_DURATION = 500;

const PoolItem = React.createClass(
  { displayName: "PoolItem"

  , propTypes:
    { handleDiskAdd  : React.PropTypes.func.isRequired
    , availableDisks : React.PropTypes.array.isRequired
    , availableSSDs  : React.PropTypes.array.isRequired
    , existsOnServer : React.PropTypes.bool
    , data           : React.PropTypes.array
    , logs           : React.PropTypes.array
    , cache          : React.PropTypes.array
    , spare          : React.PropTypes.array
    }

  , getDefaultProps: function () {
    return { existsOnServer : false
           , data           : []
           , logs           : []
           , cache          : []
           , spare          : []
           };
  }

  // The editing reconciliation model for PoolItem relies on the difference
  // between state and props. As with a simple form, the intial values are set
  // by props. Subsequent modifications to these occur in state, until an
  // update task is performed, at which time the new props will be assigned, and
  // each mutable value in state is exactly equal to its counterpart in props.
  // This pattern is also used to compare user-submitted values to upstream
  // changes. In componentWillUpdate, if we can see that the current props and
  // state have the same value for a given key, we can update the entry in the
  // client's representation without conflict. In the case that these values are
  // unequal, we can choose instead to display a warning, indicate that another
  // user has modified that field, etc. As always, the last change "wins".
  , getInitialState: function () {
    return { storageVisible  : false
           , topologyVisible : false
           , editing         : false
           , data            : this.props.data
           , logs            : this.props.logs
           , cache           : this.props.cache
           , spare           : this.props.spare
           };
  }

  , componentDidUpdate: function ( prevProps, prevState ) {

    // Toggle the display of the Storage drawer
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

    // Toggle the display of the Topology drawer
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

  , enterEditMode: function () {
    this.setState(
      { editing         : true
      , topologyVisible : true
      }
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
      { storageVisible  : false
      , topologyVisible : false
      }
    );
  }

  , render: function () {
    let storageDrawer  = null;
    let infoBarContent = null;
    let topologyDrawer = null;

    if ( this.props.existsOnServer || this.state.editing ) {
      // TODO: Conditional logic based on presence of datasets
      storageDrawer = <StorageDrawer ref="Storage" />;

      infoBarContent = (
        <TWBS.Row>
          <TWBS.Col xs={ 3 }>
            <h3>{ this.props.name }</h3>
          </TWBS.Col>
          <TWBS.Col xs={ 3 }>
            <h3>{ this.props.size }</h3>
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
              {"Show Volume"}
            </TWBS.Button>
            <TWBS.Button
              block
              bsStyle = "default"
              onClick = { this.toggleTopology }
            >
              {"Show Pool Topology"}
            </TWBS.Button>
          </TWBS.Col>
        </TWBS.Row>
      );

      topologyDrawer = (
        <TopologyDrawer
          ref            = "Topology"
          availableDisks = { this.props.availableDisks }
          availableSSDs  = { this.props.availableSSDs }
          handleDiskAdd  = { this.props.handleDiskAdd }
          data           = { this.state.data }
          logs           = { this.state.logs }
          cache          = { this.state.cache }
          spare          = { this.state.spare }
        />
      );
    } else {
      // We can reason that this is a new pool, so it should exist in an
      // "uninitialized state", waiting for the user to interact with the
      // component.
      infoBarContent = (
        <TWBS.Row
          className = "text-center text-muted"
          onClick   = { this.enterEditMode }
        >
          <h3><Icon glyph="plus" />{ "  " + this.props.newPoolMessage }</h3>
        </TWBS.Row>
      );
    }

    return (
      <TWBS.Panel>

        { storageDrawer }

        { infoBarContent }

        { topologyDrawer }

      </TWBS.Panel>
    );
  }

  }
);

export default PoolItem;
