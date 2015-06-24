// ZFS POOLS AND VOLUMES
// =====================
// This view defines a vertical stripe in the Storage page. It contains visual
// depictions of all active pools, pools which have not yet been imported, and
// also the ability to create a new storage pool. The boot pool is explicitly
// excluded from this view.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import SS from "../../stores/SchemaStore";
import VS from "../../stores/VolumeStore";
import ZM from "../../middleware/ZfsMiddleware";
import PoolItem from "./Pools/PoolItem";

const ZFS = React.createClass(

  { displayName: "ZFS"

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

  , handleDiskSelection ( event ) {
    console.log( event );
  }

  , createPoolItems ( loading, noPools ) {
    const poolItemCommon =
      { handleDiskAdd: this.handleDiskSelection
      , availableDisks: _.without( this.state.availableDisks
                                 , Array.from( this.state.selectedDisks )
                                 )
      };

    let existingPools =
      this.state.volumes.map( function ( pool, index ) {
        // The index of the "new pool" PoolItem will always be zero, so we start
        // iterating here at "1"
        return <PoolItem { ...poolItemCommon } key={ index + 1 } />;
      });

    let newPool = null;

    if ( noPools ) {
      newPool = <PoolItem { ...poolItemCommon } key={ 0 } />;
    } else {
      newPool = <PoolItem { ...poolItemCommon } key={ 0 } />;
    }

    return existingPools.concat( newPool );
  }

  , render () {
      let loading = false;
      let noPools = false;

      let statusMessage = null;

      if ( VS.isInitialized ) {
        if ( this.state.volumes.length === 0 ) {
          noPools = true;
          statusMessage = <h3>Bro, you could use a pool</h3>;
        }
      } else {
        loading = true;
        statusMessage = <h3>Looking for ZFS pools...</h3>;
      }

      return (
        <section>
          { statusMessage }
          { this.createPoolItems( loading, noPools ) }
        </section>
      );
    }

  }
);

export default ZFS;
