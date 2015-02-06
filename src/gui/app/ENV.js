// ENV
// ---
// Tiny helper shim for determining the current environment.

"use strict";

module.exports = {
    CLIENT: typeof window !== "undefined"
  , SERVER: typeof window === "undefined"
};
