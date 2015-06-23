// ZFS POOLS AND VOLUMES
// =====================
// This view defines a vertical stripe in the Storage page. It contains visual
// depictions of all active pools, pools which have not yet been imported, and
// also the ability to create a new storage pool. The boot pool is explicitly
// excluded from this view.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import VS from "../../stores/VolumeStore";
import ZM from "../../middleware/ZfsMiddleware";
import PoolItem from "./Pools/PoolItem";

const ZFS = React.createClass(

  { displayName: "ZFS"

  , getInitialState () {
      return { volumes : VS.listVolumes()
             };
    }

  , componentDidMount () {
      VS.addChangeListener( this.handleVolumesChange );

      ZM.requestVolumes();
      ZM.subscribe( this.constructor.displayName );
    }

  , componentWillUnmount () {
    VS.removeChangeListener( this.handleVolumesChange );

    ZM.unsubscribe( this.constructor.displayName );
  }

  , handleVolumesChange () {
      this.setState({
        volumes: VS.listVolumes()
      });
    }

  , createPoolItems () {
      return (
        this.state.volumes.map( pool => <PoolItem /> )
      );
    }

  , render () {
      let loadingVolumes = null;
      let noPoolsMessage = null;

      if ( VS.isInitialized ) {
        if ( this.state.volumes.length === 0 ) {
          noPoolsMessage = <h3>Bro, you could use a pool</h3>;
        }
      } else {
        loadingVolumes = <h3>Looking for ZFS pools...</h3>;
      }

      return (
        <section>
          <h1>ZFS Section Placeholder</h1>
          { this.createPoolItems() }
          { loadingVolumes }
          { noPoolsMessage }
        </section>
      );
    }

  }
);

export default ZFS;
