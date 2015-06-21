// DEBUG TOOLS EVENT BUS
// =====================
// Small event bus to assist with showing and hiding the Debug Tools pane.

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

var EventBus = _.assign( {}, EventEmitter.prototype
  , { emitToggle: function () {
        this.emit( "toggle" );
      }

    , addListener: function ( callback ) {
        this.on( "toggle", callback );
      }

    , removeListener: function ( callback ) {
        this.removeListener( "toggle", callback );
      }

    }
);

export default EventBus;
