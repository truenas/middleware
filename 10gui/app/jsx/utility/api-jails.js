// API Utility Functions
"use strict";

var request = require("request");
var _       = require("lodash");

var defaultConfig = {
    user : "root"
  , pass : "meh"
  , url  : "http://192.168.1.251"
};

// Jails
// Jails - Configuration
exports.getJailsConfiguration = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/jails/configuration/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateJailsConfiguration = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/jails/configuration/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "jc_collectionurl"        : ""         // (string) – URL for the jail index
        , "jc_ipv4_network"         : ""         // (string) – IPv4 network range for jails and plugins
        , "jc_ipv4_network_start"   : ""         // (string) – IPv4 Network Start Address
        , "jc_ipv4_network_end"     : ""         // (string) – IPv4 Network End Address
        , "jc_ipv6_network"         : ""         // (string) – IPv6 network range for jails and plugins
        , "jc_ipv6_network_start"   : ""         // (string) – IPv6 network start address for jails and plugins
        , "jc_ipv6_network_end"     : ""         // (string) – IPv6 network end address for jails and plugins
        , "jc_path"                 : ""         // (string) – dataset the jails will reside within
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

// Jails 
exports.getJails = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/jails/jails/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.addJail = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/jails/jails/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
         "jail_alias_bridge_ipv4"     : ""         // (string) – ipv4 bridge address
       , "jail_alias_bridge_ipv6"     : ""         // (string) – ipv6 bridge address
       , "jail_alias_ipv4"            : ""         // (string) – ipv4 address aliases
       , "jail_alias_ipv6"            : ""         // (string) – ipv6 address aliases
       , "jail_autostart"             : false      // (boolean) – automatically start jail at boot
       , "jail_bridge_ipv4"           : ""         // (string) – ipv4 bridge
       , "jail_bridge_ipv4_netmask"   : ""         // (string) – ipv4 netmask
       , "jail_bridge_ipv6"           : ""         // (string) – ipv6 bridge
       , "jail_bridge_ipv6_prefix"    : ""         // (string) – ipv6 prefix
       , "jail_defaultrouter_ipv4"    : ""         // (string) – ipv4 default route
       , "jail_defaultrouter_ipv6"    : ""         // (string) – ipv6 default route
       , "jail_flags"                 : ""         // (string) – sysctl jail flags
       , "jail_host"                  : ""         // (string) – hostname of the jail
       , "jail_ipv4"                  : ""         // (string) – ipv4 address of the jail
       , "jail_ipv4_netmask"          : ""         // (string) – ipv4 netmask (8, 16, 24, 32)
       , "jail_ipv6"                  : ""         // (string) – ipv6 address of the jail
       , "jail_ipv6_prefix"           : ""         // (string) – ipv6 prefix
       , "jail_mac"                   : ""         // (string) – mac address for the jail interface
       , "jail_nat"                   : false      // (boolean) – enable NAT for the jail
       , "jail_status"                : ""         // (string) – current status of the jail
       , "jail_type"                  : ""         // (string) – type of the jail (pluginjail, standard, portjail, ...)
       , "jail_vnet"                  : true       // (boolean) – enable VIMAGE for the jail
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.startJail = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/jails/jails/" + "Jail.id" + "/start/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.stopJail = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/jails/jails/" + "Jail.id" + "/stop/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteJail = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/jails/jails/" + "Jail.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

// Jails - MountPoints
exports.getMountpoints = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/jails/mountpoints/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.addMountpoint = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/jails/mountpoints/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "jail"          : ""        // (string) – name of the jail
        , "source"        : ""        // (string) – path source in the host
        , "destination"   : ""        // (string) – path destination within the jail root
        , "mounted"       : ""        // (string) – where the path is/should be mounted
        , "readonly"      : ""        // (string) – mount as read-only
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateMountpoint = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/jails/mountpoints/" + "Mountpoint.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "jail"          : ""        // (string) – name of the jail
        , "source"        : ""        // (string) – path source in the host
        , "destination"   : ""        // (string) – path destination within the jail root
        , "mounted"       : ""        // (string) – where the path is/should be mounted
        , "readonly"      : ""        // (string) – mount as read-only
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteMountpoint = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/jails/mountpoints/" + "Mountpoint.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

// Jails - Templates
exports.getTemplates = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/jails/templates/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.addTemplate = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/jails/templates/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "jt_name"           : ""        // (string) – name of the template
        , "jt_os"             : ""        // (string) – type of the OS (FreeBSD/Linux)
        , "jt_arch"           : ""        // (string) – jail architecture (x64/x86)
        , "jt_url"            : ""        // (string) – url of the template
        , "jt_instances"      : ""        // (string) – read-only, number of instances using this template
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateTemplate = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/jails/templates/" + "Template.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "jt_name"           : ""        // (string) – name of the template
        , "jt_os"             : ""        // (string) – type of the OS (FreeBSD/Linux)
        , "jt_arch"           : ""        // (string) – jail architecture (x64/x86)
        , "jt_url"            : ""        // (string) – url of the template
        , "jt_instances"      : ""        // (string) – read-only, number of instances using this template
      }    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteTemplate = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/jails/templates/" + "Template.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};