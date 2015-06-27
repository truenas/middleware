// ZFS POOLS AND VOLUMES - STORAGE
// ===============================
// This view is defined by vertical stripes in the Storage page. It contains
// depictions of all active pools, pools which have not yet been imported, and
// also the ability to create a new storage pool. The boot pool is explicitly
// excluded from this view.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import SS from "../stores/SchemaStore";
import VS from "../stores/VolumeStore";
import ZM from "../middleware/ZfsMiddleware";
import Volume from "./Storage/Volume";

const Storage = React.createClass(

  { displayName: "Storage"

  , getInitialState () {
      return { volumes        : VS.listVolumes()
             , availableDisks : VS.availableDisks
             , selectedDisks  : new Set()
             };
    }

  , componentDidMount () {
      VS.addChangeListener( this.handleStoreChange );

      ZM.requestVolumes();
      ZM.requestAvailableDisks();
      ZM.subscribe( this.constructor.displayName );
    }

  , componentWillUnmount () {
      VS.removeChangeListener( this.handleVolumesChange );

      ZM.unsubscribe( this.constructor.displayName );
    }

  , handleStoreChange ( eventMask ) {
      this.setState(
        { volumes        : VS.listVolumes()
        , availableDisks : VS.availableDisks
        }
      );
    }

  , handleDiskAdd ( event ) {
    console.log( event );
  }

  , handleDiskRemove ( event ) {
    console.log( event );
  }

  , createVolumes ( loading, noVolumes ) {
      const volumeCommon =
        { handleDiskAdd: this.handleDiskAdd
        , availableDisks: _.without( this.state.availableDisks
                                   , Array.from( this.state.selectedDisks )
                                   )
        , availableSSDs: [] // FIXME
        };

      let existingPools =
        this.state.volumes.map( function ( volume, index ) {
          let { data, logs, cache, spare } = volume.topology;
          let { free, allocated, size }    = volume.properties;

          // The index of the "new pool" Volume will always be zero, so we
          // start keying here at "1"
          return (
            <Volume
              { ...volumeCommon }
              existsOnServer
              data      = { data }
              logs      = { logs }
              cache     = { cache }
              spare     = { spare }
              free      = { free.value }
              allocated = { allocated.value }
              size      = { size.value }
              datasets  = { volume.datasets }
              name      = { volume.name }
              key       = { index + 1 }
            />
          );
        });

      let newPool = null;

      if ( noVolumes ) {
        newPool =
          <Volume { ...volumeCommon }
            key = { 0 }
            newPoolMessage = { "Create your first ZFS pool" }
          />;
      } else {
        newPool =
          <Volume { ...volumeCommon }
            key = { 0 }
            newPoolMessage = { "Create a new ZFS pool" }
          />;
      }

      return existingPools.concat( newPool );
    }

  , render () {
      let loading = false;
      let noVolumes = false;

      let statusMessage = null;

      if ( VS.isInitialized ) {
        if ( this.state.volumes.length === 0 ) {
          noVolumes = true;
          statusMessage = <h3>Bro, you could use a pool</h3>;
        }
      } else {
        loading = true;
        statusMessage = <h3>Looking for ZFS pools...</h3>;
      }

      return (
        <main>
          { statusMessage }
          { this.createVolumes( loading, noVolumes ) }
        </main>
      );
    }

  }
);

export default Storage;
