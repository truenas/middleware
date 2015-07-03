// ZFS POOL / VOLUME ITEM
// ======================
// Individual item which represents a ZFS pool and its associated volume.
// Contains the datasets, ZVOLs, and other high level objects that are
// properties of the pool.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import ByteCalc from "../../common/ByteCalc";
import BreakdownChart from "./Volumes/BreakdownChart";
import PoolDatasets from "./Volumes/PoolDatasets";
import PoolTopology from "./Volumes/PoolTopology";

const SLIDE_DURATION = 500;

const PoolItem = React.createClass(
  { displayName: "PoolItem"

  , propTypes:
    { handleDiskAdd          : React.PropTypes.func.isRequired
    , handleDiskRemove       : React.PropTypes.func.isRequired
    , handleVdevAdd          : React.PropTypes.func.isRequired
    , handleVdevRemove       : React.PropTypes.func.isRequired
    , handleVdevTypeChange   : React.PropTypes.func.isRequired
    , handleVolumeReset      : React.PropTypes.func.isRequired
    , handleVolumeNameChange : React.PropTypes.func.isRequired
    , submitVolume           : React.PropTypes.func.isRequired
    , availableDisks         : React.PropTypes.array.isRequired
    , availableSSDs          : React.PropTypes.array.isRequired
    , existsOnServer         : React.PropTypes.bool
    , data                   : React.PropTypes.array
    , logs                   : React.PropTypes.array
    , cache                  : React.PropTypes.array
    , spares                 : React.PropTypes.array
    , free: React.PropTypes.oneOfType(
        [ React.PropTypes.string
        , React.PropTypes.number
        ]
      )
    , allocated: React.PropTypes.oneOfType(
        [ React.PropTypes.string
        , React.PropTypes.number
        ]
      )
    , size: React.PropTypes.oneOfType(
        [ React.PropTypes.string
        , React.PropTypes.number
        ]
      )
    , datasets        : React.PropTypes.array
    , name            : React.PropTypes.string
    , volumeKey       : React.PropTypes.number.isRequired
    , volumesOnServer : React.PropTypes.array.isRequired
    }

  , getDefaultProps: function () {
    return { data           : []
           , logs           : []
           , cache          : []
           , spares         : []
           , free           : 0
           , allocated      : 0
           , size           : 0
           };
  }

  , returnInitialStateValues: function () {
    return { storageVisible  : this.props.existsOnServer
           , topologyVisible : !this.props.existsOnServer
           , editing         : !this.props.existsOnServer
           , data            : this.props.data
           , logs            : this.props.logs
           , cache           : this.props.cache
           , spares          : this.props.spares
           , free            : this.props.free
           , allocated       : this.props.allocated
           , size            : this.props.size
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
    return this.returnInitialStateValues();
  }

  // A shorthand method used to "cancel" creation or editing of a volume.
  // TODO: This should probably be gated so that it isn't triggered without a
  // warning to the user.
  , resetToInitialState: function () {
    this.setState( this.returnInitialStateValues() );
  }

  , componentDidMount: function () {
    // When the volume doesn't exist on the server, topology should start open.
    if ( !this.props.existsOnServer ) {
      Velocity( React.findDOMNode( this.refs.Topology )
                , "slideDown"
                , SLIDE_DURATION
                );
    }
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
    let datasets  = null;
    let infoBar = null;
    let volumeNameField = null;
    let volumeSubmitLabel = "";
    let volumeSubmitButton = null;
    let topology = null;

    if ( this.props.existsOnServer || this.state.editing ) {
      let freeSize      = ByteCalc.convertString( this.props.free );
      let allocatedSize = ByteCalc.convertString( this.props.allocated );
      let totalSize     = ByteCalc.convertString( this.props.size );

      // TODO: Conditional logic based on presence of datasets
      datasets = <PoolDatasets ref="Storage" />;

      infoBar = (
        <TWBS.Row>
          <TWBS.Col xs={ 3 }>
            <h3>{ this.props.name }</h3>
          </TWBS.Col>
          <TWBS.Col xs={ 3 }>
            <h3>{ ByteCalc.humanize( totalSize ) }</h3>
          </TWBS.Col>
          <TWBS.Col xs={ 4 }>
            <BreakdownChart
              free   = { freeSize }
              used   = { allocatedSize }
              parity = { totalSize / 4 /* FIXME */ }
              total  = { totalSize }
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

      volumeNameField = (
        <TWBS.Input
          type = "text"
          onChange = { this.props.handleVolumeNameChange.bind( null
                                                             , this.props.volumeKey
                                                             )
                     }
          placeholder = "Volume Name"
          value = { this.props.name }
        />
      );

      volumeSubmitLabel = this.props.existsOnServer
                        ? "Submit Volume Changes"
                        : "Submit New Volume";

      volumeSubmitButton = (
        <TWBS.Button
          bsStyle = "default"
          onClick = { this.props.submitVolume.bind( null
                                                  , this.props.volumeKey
                                                  )
                    }
        >
          { volumeSubmitLabel }
        </TWBS.Button>
      );

      topology = (
        <PoolTopology
          ref                  = "Topology"
          availableDisks       = { this.props.availableDisks }
          availableSSDs        = { this.props.availableSSDs }
          handleDiskAdd        = { this.props.handleDiskAdd }
          handleDiskRemove     = { this.props.handleDiskRemove }
          handleVdevAdd        = { this.props.handleVdevAdd }
          handleVdevRemove     = { this.props.handleVdevRemove }
          handleVdevTypeChange = { this.props.handleVdevTypeChange }
          data                 = { this.state.data }
          logs                 = { this.state.logs }
          cache                = { this.state.cache }
          spares               = { this.state.spares }
          volumeKey            = { this.props.volumeKey }
          volumesOnServer      = { this.props.volumesOnServer }
        />
      );
    }

    return (
      <TWBS.Panel>

        { datasets }

        { infoBar }

        { volumeNameField }

        { volumeSubmitButton }

        { topology }

      </TWBS.Panel>
    );
  }

  }
);

export default PoolItem;
