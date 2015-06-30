// FreeNAS Constants
// -----------------
// Objects containing constant mirrored key-value pairs for use with Flux stores
// and dispatcher. Simple way to maintain consistency for actions and sources.

import keyMirror from "keymirror";

const FREENAS_CONSTANTS =
  { ActionTypes: keyMirror(
    // Authentication, Socket State and other SID stuff
    { UPDATE_AUTH_STATE: null
    , UPDATE_SOCKET_STATE: null
    , UPDATE_RECONNECT_TIME : null

    // Subscriptions
    , SUBSCRIBE_COMPONENT_TO_MASKS: null
    , UNSUBSCRIBE_COMPONENT_FROM_MASKS: null
    , UNSUBSCRIBE_ALL: null

    // Events
    , MIDDLEWARE_EVENT: null

    // Tasks
    , RECEIVE_TASK_HISTORY: null

    // RPC
    , RECEIVE_RPC_SERVICES: null
    , RECEIVE_RPC_SERVICE_METHODS: null

    // Users
    , RECEIVE_RAW_USERS: null
    , RECEIVE_USER_UPDATE_TASK: null

    // Groups
    , RECEIVE_GROUPS_LIST: null
    , RECEIVE_GROUP_UPDATE_TASK: null

    // Services
    , RECEIVE_MIDDLEWARE_SCHEMAS: null
    , RECEIVE_RAW_SERVICES: null
    , RECEIVE_SERVICE_UPDATE_TASK: null

    // Widget Data
    , RECEIVE_RAW_WIDGET_DATA: null

    // System Data
    , RECEIVE_SYSTEM_INFO_DATA: null
    , RECEIVE_SYSTEM_DEVICE_DATA: null
    , RECEIVE_SYSTEM_GENERAL_CONFIG_DATA: null
    , RECEIVE_SYSTEM_GENERAL_CONFIG_UPDATE: null

    // Update Data
    , RECEIVE_UPDATE_DATA: null

    // Global Network Configuration
    , RECEIVE_NETWORK_CONFIG: null
    , RECEIVE_NETWORK_CONFIG_UPDATE: null

    // Interfaces
    , RECEIVE_INTERFACES_LIST: null
    , RECEIVE_INTERFACE_CONFIGURE_TASK: null
    , RECEIVE_UP_INTERFACE_TASK: null
    , RECEIVE_DOWN_INTERFACE_TASK: null

    // ZFS
    , RECEIVE_VOLUMES: null
    , RECEIVE_AVAILABLE_DISKS: null
    , RECEIVE_POOL: null
    , RECEIVE_BOOT_POOL: null
    , RECEIVE_POOL_DISK_IDS: null

    // Disks
    , RECEIVE_DISKS_OVERVIEW: null
    , RECEIVE_DISK_DETAILS: null
    })

  , PayloadSources: keyMirror(
    { MIDDLEWARE_ACTION: null
    , MIDDLEWARE_LIFECYCLE: null
    , CLIENT_ACTION: null
    })
  };

export default FREENAS_CONSTANTS;