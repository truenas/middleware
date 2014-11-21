// FreeNAS Constants
// -----------------
// Objects containing constant mirrored key-value pairs for use with Flux stores
// and dispatcher. Simple way to maintain consistency for actions and sources.

var keyMirror = require("keymirror");

module.exports = {
    ActionTypes: keyMirror({
        RECEIVE_RAW_USERS : null
    })
  , PayloadSources: keyMirror({
        MIDDLEWARE_ACTION : null
      , CLIENT_ACTION     : null
  })
};