// STORE LIMITS
// ============
// A set of configurable constants to be used by Flux stores. These values set
// the maximum number of records that will / should be stored by by a specific
// store, and should also be used as a limit parameter in the original query,
// if possible.

// This may be replaced some day by user preferences, dynamic scaling, or some
// other more complicated solution.

"use strict";

import keyMirror from "keymirror";

const STORE_LIMITS =
  { DISKS: Infinity
  , GROUPS: Infinity
  , INTERFACES: Infinity
  , SERVICES: Infinity
  , TASKS: Infinity
  , USERS: Infinity
  };

export default STORE_LIMITS;
