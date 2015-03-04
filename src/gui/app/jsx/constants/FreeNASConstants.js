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

      // Events
      , MIDDLEWARE_EVENT          : null
      , LOG_MIDDLEWARE_TASK_QUEUE : null

      // Users
      , RECEIVE_RAW_USERS        : null
      , RECEIVE_USER_UPDATE_TASK : null
      , RESOLVE_USER_UPDATE_TASK : null

      // Services
      , RECEIVE_RAW_SERVICES : null

      //Widget Data
      , RECEIVE_RAW_WIDGET_DATA : null

      //SystemInfo Data
      , RECEIVE_SYSTEM_INFO_DATA : null

      //Update Data
      , RECEIVE_UPDATE_DATA : null

      //Networks
      , RECEIVE_RAW_NETWORKS        : null
      , RECEIVE_NETWORK_UPDATE_TASK : null
      , RESOLVE_NETWORK_UPDATE_TASK : null
    })

  , PayloadSources: keyMirror({
        MIDDLEWARE_ACTION    : null
      , MIDDLEWARE_LIFECYCLE : null
      , CLIENT_ACTION        : null
    })

};