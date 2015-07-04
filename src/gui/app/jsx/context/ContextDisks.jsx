// Contextual Disks Display
// ========================
// A contextual popout for use with the ContextBar component. Displays icons
// for all disks that are not part of a volume so that they may be used for
// new vdev creation.

"use strict";

import React from "react";
import _ from "lodash";
import TWBS from "react-bootstrap";

import SS from "../stores/SchemaStore"
import DS from "../stores/DisksStore";
import DM from "../middleware/DisksMiddleware";
import VS from "../stores/VolumeStore";
import ZM from "../middleware/ZfsMiddleware";

import DiskItemIcon from "../views/Storage/Disks/DiskItemIcon";

const ContextDisks = React.createClass(

  { displayName: "Contextual Disks Drawer"

  , getInitialState () {

    let initialState = this.populateDisks();

    _.assign( initialState, { diskSchema: SS.getDef( "disk" ) } );

    return initialState;
  }

  , componentDidMount () {
    DS.addChangeListener( this.handleChange );
    DM.subscribe( this.constructor.displayName );
    DM.requestDisksOverview();

    VS.addChangeListener( this.handleChange );

    ZM.subscribe( this.constructor.displayName );

    ZM.requestVolumes();
    ZM.requestAvailableDisks();
  }

  , componentWillUnmount () {
    DS.removeChangeListener( this.handleChange );
    DM.unsubscribe( this.constructor.displayName );

    VS.removeChangeListener( this.handleChange );

    ZM.unsubscribe( this.constructor.displayName );
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

  // Produce a TWBS Row displaying all the disks where the filterKey matches the
  // filterValue.
  , createDisksDisplaySection ( filterKey, filterValue ) {

    let displayArray =
    _.filter( this.state.availableDisks
      , function filterDisks ( disk ) {
        return ( !_.has( disk, filterKey, this )
              || disk[ filterKey ] === filterValue
               );
      }
      , this
      );

    let diskItems =
      _.map( displayArray
           , function addDiskItem ( disk ) {
             return (
              <TWBS.Col
                xs = {6} >
                <DiskItemIcon { ...disk } />
              </TWBS.Col> );
           }
           , this
           );

    return (
        <TWBS.Row>
          { diskItems }
        </TWBS.Row>
    );
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
      disksDisplay = this.createDisksDisplaySection( "is-ssd", false );
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
        { disksDisplay }
      </TWBS.Grid>

    );
  }

});

export default ContextDisks;
