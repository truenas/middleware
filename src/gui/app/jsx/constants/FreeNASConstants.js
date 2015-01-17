// FreeNAS Constants
// -----------------
// Objects containing constant mirrored key-value pairs for use with Flux stores
// and dispatcher. Simple way to maintain consistency for actions and sources.

var keyMirror = require("keymirror");

module.exports = {
    ActionTypes: keyMirror({
        UPDATE_AUTH_STATE : null

      // Subscriptions
      , SUBSCRIBE_TO_MASK     : null
      , UNSUBSCRIBE_FROM_MASK : null

      , LOG_MIDDLEWARE_EVENT      : null
      , LOG_MIDDLEWARE_TASK_QUEUE : null

      // Users
      , RECEIVE_RAW_USERS        : null
      , RECEIVE_CHANGED_USER_IDS : null

      // Services
      , RECEIVE_RAW_SERVICES : null
    })
  , PayloadSources: keyMirror({
        MIDDLEWARE_ACTION    : null
      , MIDDLEWARE_LIFECYCLE : null
      , CLIENT_ACTION        : null
    })
};