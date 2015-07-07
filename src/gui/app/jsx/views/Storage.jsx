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

import EventBus from "../components/EventBus";
import Icon from "../components/Icon";

import ContextDisks from "../context/ContextDisks";

import SS from "../stores/SchemaStore";
import VS from "../stores/VolumeStore";
import ZM from "../middleware/ZfsMiddleware";

import Volume from "./Storage/Volume";

const Storage = React.createClass(

  { displayName: "Storage"

  , getInitialState () {

    return ( { volumes         : VS.listVolumes()
             , selectedDisks   : new Set()
             }
           );
  }

  , componentDidMount () {
    VS.addChangeListener( this.handleVolumesChange );

    ZM.requestVolumes();
    ZM.requestAvailableDisks();
    ZM.subscribe( this.constructor.displayName );

    EventBus.emit( "showContextPanel", ContextDisks );
  }

  , componentWillUnmount () {
    VS.removeChangeListener( this.handleVolumesChange );

    ZM.unsubscribe( this.constructor.displayName );

    EventBus.emit( "hideContextPanel", ContextDisks );
  }

  , handleVolumesChange ( eventMask ) {
    this.setState(
      { volumes: VS.listVolumes() }
    );
  }

  , createNewDisk ( path ) {
    return ( { path: path
             , type: "disk"
             , children: []
             }
    );
  }

    // TODO: Accept different types of events, allowing for multiple disks, a
    // variety of disk types and various means of adding disks (drag and drop,
    // multiselect, etc.)
    // TODO: Reasonable recommendations (both initial and changed as needed) for
    // Different numbers of disks.
  , handleDiskAdd ( volumeKey, vdevPurpose, vdevKey, event ) {

    let newSelectedDisks = null;
    let newVolumes = this.state[ "volumes" ];
    let newVdev = this.state[ "volumes" ]
                            [ volumeKey ]
                            [ "topology" ]
                            [ vdevPurpose ]
                            [ vdevKey ];

    switch ( newVdev.type ) {
      // All non-disk vdevs will just need the new disk added to their children.
      case "raidz3" :
      case "raidz2" :
      case "raidz1" :
      case "mirror" :
        newVdev.children.push( this.createNewDisk( event.target.value ) );
        break;

      case "disk" :
        newVdev.type = "mirror";
        newVdev.children = [ this.createNewDisk( newVdev.path )
                           , this.createNewDisk( event.target.value )
                           ];
        newVdev.path = null;
        break;

      // Fresh Vdev with no type becomes a disk and obtains the target as its
      // path.
      default:
        newVdev = this.createNewDisk( event.target.value );
        break;
    }

    newVolumes[ volumeKey ][ "topology" ][ vdevPurpose ][ vdevKey ] = newVdev;

    // Last-second bailout if the disk path is invalid
    if ( _.any( VS.availableDisks
              , function checkAvailableDisks ( disk ) {
                return ( disk === event.target.value );
              }
              , this
              )
       ) {

      newSelectedDisks = this.state.selectedDisks.add( event.target.value );

      this.setState( { volumes: newVolumes
                     , selectedDisks: newSelectedDisks
                     }
                   );
    }

  }

  , handleDiskRemove ( volumeKey, vdevPurpose, vdevKey, diskPath ) {

    let newVolumes = this.state[ "volumes" ];
    let newVdev = this.state[ "volumes" ]
                            [ volumeKey ]
                            [ "topology" ]
                            [ vdevPurpose ]
                            [ vdevKey ];

    switch ( newVdev.type ) {

      case "raidz3" :
        if ( newVdev.children.length === 5 ) {
          _.pull( newVdev.children, diskPath );
          newVdev.type = "raidz2";
        } else {
          _.pull( newVdev.children, diskPath );
        }
        break;

      case "raidz2" :
        if ( newVdev.children.length === 4 ) {
          _.pull( newVdev.children, diskPath );
          newVdev.type = "raidz1";
        } else {
          _.pull( newVdev.children, diskPath );
        }
        break;

      case "raidz1" :

        if ( newVdev.children.length === 3 ) {
          _.pull( newVdev.children, diskPath );
          newVdev.type = "mirror";
        } else {
          _.pull( newVdev.children, diskPath );
        }
        break;

      case "mirror" :
        if ( newVdev.children.length === 2 ) {
          newVdev.children = [];
          newVdev.path = diskPath;
          newVdev.type = "disk";
        } else {
          _.pull( newVdev.children, diskPath );
        }
        break;

      case "disk" :
        newVdev.type = null;
        newVdev.path = null;
        break;

      default:
        break;
    }

    newVolumes[ volumeKey ][ "topology" ][ vdevPurpose ][ vdevKey ] = newVdev;

    let newSelectedDisks = this.state.selectedDisks;

    newSelectedDisks.delete( diskPath );

    this.setState( { volumes: newVolumes
                   , selectedDisks: newSelectedDisks
                   }
                 );

  }

    // This is exclusively for adding a new, empty vdev at the top level of a
    // volume topology. Adding new disks is handled by 'handleDiskAdd' and
    // 'createNewDisk'.
  , handleVdevAdd ( volumeKey, vdevPurpose ) {
    let newVolumes = this.state[ "volumes" ];

    // This will be more sophisticated in the future.
    let newVdev = { children : []
                  , path     : null
                  , type     : null
                  };

    if ( !newVolumes[ volumeKey ][ "topology" ][ vdevPurpose ] ) {
      newVolumes[ volumeKey ][ "topology" ][ vdevPurpose ] = [];
    }

    newVolumes[ volumeKey ][ "topology" ][ vdevPurpose ].push( newVdev );

    this.setState( { volumes: newVolumes } );
  }

  , handleVdevRemove ( event, volumeKey, vdevKey ) {
    console.log( "handleVdevRemove", event, volumeKey, vdevKey );
  }

  , handleVdevTypeChange ( event, volumeKey, vdevKey, newVdevType ) {
    console.log(
      "handleVdevTypeChange"
      , event
      , volumeKey
      , vdevKey
      , newVdevType
    );
  }

  , handleVolumeAdd ( event ) {
    let newVolumes = this.state[ "volumes" ];

    newVolumes.push( this.generateFreshVolume() );

    this.setState( { volumes: newVolumes } );
  }

  , handleVolumeReset ( event, volumeKey ) {
    let newVolumes = this.state[ "volumes" ];

    newVolumes[ volumeKey ] = this.generateFreshVolume();

    this.setState( { volumes: newVolumes } );
  }

  , handleVolumeNameChange ( volumeKey, event ) {
    let newVolumes = this.state[ "volumes" ];

    newVolumes[ volumeKey ][ "name" ] = event.target.value;

    this.setState( { volumes: newVolumes } );
  }

    // TODO: Validate against the actual schema
    // TODO: Remove read-only fields and anything that should not be submitted
    // with a new volume. These are not necessarily listed in the schema yet.
  , submitVolume ( volumeKey, event ) {
    ZM.submitVolume( this.state.volumes[ volumeKey ] );
  }

  , generateFreshVolume () {
    return ( { topology   : { data  : []
                            , logs  : []
                            , cache : []
                            , spares : []
                            }
             , properties : { free      : 0
                            , allocated : 0
                            , size      : 0
                            }
             , type: "zfs" // This will never change for a ZFS volume
             , name: ""
             }
           );
  }

  , createVolumes ( loading ) {
    const volumeCommon =
      { handleDiskAdd          : this.handleDiskAdd
      , handleDiskRemove       : this.handleDiskRemove
      , handleVdevAdd          : this.handleVdevAdd
      , handleVdevRemove       : this.handleDiskRemove
      , handleVdevTypeChange   : this.handleVdevTypeChange
      , handleVolumeReset      : this.handleVolumeReset
      , handleVolumeNameChange : this.handleVolumeNameChange
      , submitVolume           : this.submitVolume
      , availableDisks: _.without( VS.availableDisks
                                 , ...Array.from( this.state.selectedDisks )
                                 )
      , availableSSDs: [] // FIXME
      // This must be submitted in full because it is also necessary to know
      // which vdevs of an existing volume were added in editing and which
      // already existed and thus may not be deleted.
      , volumesOnServer: VS.listVolumes()
      };

    let pools =
      this.state.volumes.map( function ( volume, index ) {
        let { data, logs, cache } = volume.topology;
        let { free, allocated, size }    = volume.properties;

        let spares = volume.topology[ "spares" ] || [];

        // existsOnServer: a new volume will have an equal or higher index
        // than the number of volumes known to the server.
        // volumeKey: Used to note which volume in the array is being
        // modified, so it is simply the index of that volume in the array.
        return (
          <Volume
            { ...volumeCommon }
            existsOnServer = { index < VS.listVolumes().length }
            data      = { data }
            logs      = { logs }
            cache     = { cache }
            spares    = { spares }
            free      = { free.value }
            allocated = { allocated.value }
            size      = { size.value }
            datasets  = { volume.datasets }
            name      = { volume.name }
            volumeKey = { index }
            key       = { index }
          />
        );
      }.bind( this ) );

    return pools;
  }

  , render () {
    let loading = false;

    let statusMessage = null;

    let newPool = null;

    let newPoolMessage = "";

    if ( VS.isInitialized ) {
      if ( this.state.volumes.length === 0 ) {
        statusMessage = <h3>Bro, you could use a pool</h3>;
        newPoolMessage = "Create your first ZFS pool";
      } else {
        newPoolMessage = "Create a new ZFS pool";
      }
      newPool = (
      <TWBS.Panel>
        <TWBS.Row
          className = "text-center text-muted"
          onClick   = { this.handleVolumeAdd } >
          <h3><Icon glyph="plus" />{ "  " + newPoolMessage }</h3>
        </TWBS.Row>
      </TWBS.Panel>
    );
    } else {
      loading = true;
      statusMessage = <h3>Looking for ZFS pools...</h3>;
    }

    return (
      <main>
        { statusMessage }

        { this.createVolumes( loading ) }

        { newPool }
      </main>
    );
  }

});

export default Storage;
