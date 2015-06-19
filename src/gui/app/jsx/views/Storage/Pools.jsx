// ZFS POOLS AND VOLUMES
// =====================
// This view defines a vertical stripe in the Storage page. It contains visual
// depictions of all active pools, pools which have not yet been imported, and
// also the ability to create a new storage pool. The boot pool is explicitly
// excluded from this view.

"use strict";

import React from "react";

import ZS from "../../stores/ZfsStore";
import ZM from "../../middleware/ZfsMiddleware";
import PoolItem from "./Pools/PoolItem";

const Pools = React.createClass(

  { displayName: "Pools"

  , getInitialState () {
      return {
        pools: ZS.listStoragePools()
      };
    }

  , componentDidMount () {
      ZS.addChangeListener( this.handlePoolsChange );
      ZM.requestVolumes();
      ZM.subscribe( this.constructor.displayName );
    }

  , componentWillUnmount () {
    ZS.removeChangeListener( this.handlePoolsChange );
    ZM.unsubscribe( this.constructor.displayName );
  }

  , handlePoolsChange () {
      this.setState({
        pools: ZS.listStoragePools()
      });
    }

  , createPoolItems () {
      return (
        this.state.pools.map( pool => <PoolItem /> )
      );
    }

  , render () {
      return (
        <section>
          <h1>Pools Section Placeholder</h1>
          { this.createPoolItems() }
        </section>
      );
    }

  }
);

export default Pools;
