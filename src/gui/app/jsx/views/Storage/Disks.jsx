// DISKS VIEW
// ==========
// Overview of all the hard disks in your FreeNAS system.

"use strict";

import React from "react";

import ByteCalc from "../../common/ByteCalc";
import Viewer from "../../components/Viewer";

import DS from "../../stores/DisksStore";
import DM from "../../middleware/DisksMiddleware";

const VIEWER_DATA =
  { keyUnique     : DS.uniqueKey
  , keyPrimary    : "path"
  , keySecondary  : "serial"

  , itemSchema    : DS.itemSchema
  , itemLabels    : DS.itemLabels

  , routeName     : "disk-item-view"
  , routeParam    : "diskSerial"

  , textRemaining : "Other disks"
  , textUngrouped : "All disks"

  , columnsInitial : new Set(
                      [ "serial"
                      , "path"
                      , "online"
                      , "byteSize"
                      ]
                    )
  , columnsAllowed : new Set(
                      [ "serial"
                      , "path"
                      , "online"
                      , "byteSize"
                      ]
                    )

  , groupBy:
    { online:
       { name: "Currently Online"
       , testProp: { online: true }
       }
    }

  , groupsInitial : new Set( [ "online" ] )
  , groupsAllowed : new Set( )
  };

function getDisksFromStore () {
  return { disks: DS.getDisksArray() };
}

const Disks = React.createClass(

  { getInitialState: function () {
      return getDisksFromStore();
    }

  , componentDidMount: function () {
      DS.addChangeListener( this.handleDisksChange );
      DM.requestDisksOverview();
      DM.subscribe( this.constructor.displayName );
    }

  , componentWillUnmount: function () {
      DS.removeChangeListener( this.handleDisksChange );
      DM.unsubscribe( this.constructor.displayName );
    }

  , handleDisksChange: function () {
      this.setState( getDisksFromStore() );
    }

  , render: function () {
      return (
        <Viewer { ...VIEWER_DATA }
          header   = "Disks"
          itemData = { this.state.disks }
        />
      );
    }

  }

);

export default Disks;
