// FREENAS UTIL
// ============
// This module contains a set of common utility functions which have broad
// applicability to different areas of the FreeNAS WebApp. They may be used in
// React Components, Flux Stores, or entirely separate places.

"use strict";

var freeNASUtil = exports;

// Generates a unique UUID which a client includes with each call (generally
// within the `pack` function). This ID may then be used to verify either the
// original client or for the client to verify the middleware's response.
freeNASUtil.generateUUID = function() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace( /[xy]/g, function (c) {
      var r = Math.random() * 16 | 0;
      var v = ( c === "x" ) ? r : ( r & 0x3 | 0x8 );

      return v.toString(16);
    }
  );
};
