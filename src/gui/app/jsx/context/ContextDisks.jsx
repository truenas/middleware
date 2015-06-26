// Contextual Disks Display
// ========================
// A contextual popout for use with the ContextBar component. Displays icons
// for all disks that are not part of a volume so that they may be used for
// new vdev creation.

"use strict";

const componentLongName = "ContextDisks";

import React from "react";
import _ from "lodash";

import SS from "../stores/SchemaStore"
import DS from "../stores/DisksStore";
import DM from "../middleware/DisksMiddleware";
import VS from "../stores/VolumeStore";
import ZM from "../middleware/ZfsMiddleware";

import DiskItemIcon from "../views/Storage/Disks/DiskItemIcon";

const ContextDisks = React.createClass({

  getInitialState () {
    return ( { disks: DS.disksArray
             , availableDisks: VS.availableDisks
             , diskSchema: SS.getDef( "disk" )
             }
           );
  }

  , componentDidMount () {
    DS.addChangeListener( this.handleDisksChange );
    DM.subscribe( componentLongName );
    DM.requestDisksOverview();

    VS.addChangeListener( this.handleVolumeChange );

    ZM.subscribe( componentLongName );

    ZM.requestVolumes();
    ZM.requestAvailableDisks();
  }

  , componentWillUnmount () {
    DS.removeChangeListener( this.handleDisksChange );
    DM.unsubscribe( componentLongName );

    VS.removeChangeListener( this.handleVolumeChange );

    ZM.unsubscribe( componentLongName );
  }

  , handleDisksChange () {
    this.setState( { disks: DS.disksArray
                   , availableDisks: VS.availableDisks
                   }
                 );
  }

  , handleVolumeChange () {
    this.setState( { availableDisks: VS.availableDisks } );
  }

  , render () {

    return (
      <h4>
        { "Available Disks" }
      </h4>
    );
  }

});

export default ContextDisks;
