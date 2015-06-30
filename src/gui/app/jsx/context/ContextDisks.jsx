// Contextual Disks Display
// ========================
// A contextual popout for use with the ContextBar component. Displays icons
// for all disks that are not part of a volume so that they may be used for
// new vdev creation.

"use strict";

const componentLongName = "ContextDisks";

import React from "react";
import _ from "lodash";
import TWBS from "react-bootstrap";

import SS from "../stores/SchemaStore"
import DS from "../stores/DisksStore";
import DM from "../middleware/DisksMiddleware";
import VS from "../stores/VolumeStore";
import ZM from "../middleware/ZfsMiddleware";

import DiskItemIcon from "../views/Storage/Disks/DiskItemIcon";

const ContextDisks = React.createClass({

  getInitialState () {

    let initialState = this.populateDisks();

    _.assign( initialState, { diskSchema: SS.getDef( "disk" ) } );

    return initialState;
  }

  , componentDidMount () {
    DS.addChangeListener( this.handleChange );
    DM.subscribe( componentLongName );
    DM.requestDisksOverview();

    VS.addChangeListener( this.handleChange );

    ZM.subscribe( componentLongName );

    ZM.requestVolumes();
    ZM.requestAvailableDisks();
  }

  , componentWillUnmount () {
    DS.removeChangeListener( this.handleChange );
    DM.unsubscribe( componentLongName );

    VS.removeChangeListener( this.handleChange );

    ZM.unsubscribe( componentLongName );
  }

  , populateDisks () {

    var disks = DS.disksArray;

    let availableDisks = _.map( VS.availableDisks
                              , function mapAvailableDisks ( diskPath ) {
                                return ( _.find( disks
                                               , { path: diskPath }
                                               , this
                                               )
                                       );
                              }
                          , this
                          );

    return { disks: disks
           , availableDisks: availableDisks
           };
  }

  , handleChange () {

    let newDisksInformation = this.populateDisks();

    this.setState( newDisksInformation );
  }

  , createDisksDisplay () {

  }

  , render () {

    let filterControls = null;
    let disksDisplay = null;

    if ( this.state.availableDisks.length === 0 ) {
      disksDisplay = (
        <div>
          { "You don't have any available disks" }
        </div>
      );
    } else {
      disksDisplay = this.createDisksDisplay();
    }

    return (
      <TWBS.Grid fluid>
        <TWBS.Row>
          <TWBS.Col xs = { 4 } >
            <h4>
              { "Available Disks: " + this.state.availableDisks.length }
            </h4>
          </TWBS.Col>
          <TWBS.Col xs = { 8 } >
            { filterControls }
          </TWBS.Col>
        </TWBS.Row>
        <TWBS.Row>
          <TWBS.Col>
            { disksDisplay }
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>

    );
  }

});

export default ContextDisks;
