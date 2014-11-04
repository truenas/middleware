// API Utility Functions
"use strict";

var request = require("request");
var _       = require("lodash");

var defaultConfig = {
    user : "root"
  , pass : "meh"
  , url  : "http://192.168.1.251"
};

// Network
// Network - Global Configuration
exports.getNetworkConfiguration = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/network/globalconfiguration/?format=json"
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

exports.updateNetworkConfiguration = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/network/globalconfiguration/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "gc_domain"            : ""          // (string) – domain
        , "gc_hostname"          : ""          // (string) – hostname
        , "gc_ipv4gateway"       : ""          // (string) – ipv4 address of the gateway
        , "gc_ipv6gateway"       : ""          // (string) – ipv6 address of the gateway
        , "gc_nameserver1"       : ""          // (string) – nameserver address #1
        , "gc_nameserver2"       : ""          // (string) – nameserver address #2
        , "gc_nameserver3"       : ""          // (string) – nameserver address #3
        , "gc_netwait_enabled"   : true        // (boolean) – enable netwait feature
        , "gc_netwait_ip"        : ""          // (string) – list of IPs to wait before proceed the boot
        , "gc_hosts"             : ""          // (string) – entries to append to /etc/hosts
        , "gc_httpproxy"         : ""          // (string) – http_proxy ip:port

      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

// Network - Interfaces
exports.getInterfaces = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/network/interface/?format=json"
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

exports.addInterface = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/network/interface/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "int_name"             : ""            // (string) – user name for the interface
        , "int_interface"        : ""            // (string) – name of the physical interface
        , "int_ipv4address"      : ""            // (string) – main IPv4 address
        , "int_v4netmaskbit"     : ""            // (string) – number of bits for netmask (1..32)
        , "int_ipv6address"      : ""            // (string) – main IPv6 address
        , "int_v6netmaskbit"     : ""            // (string) – number of bits for netmask [0, 48, 60, 64, 80, 96]
        , "int_dhcp"             : true          // (boolean) – enable DHCP
        , "int_ipv6auto"         : true          // (boolean) – enable auto IPv6
        , "int_options"          : ""            // (string) – extra options to ifconfig(8)
        , "int_aliases"          : ""            // (list(string)) – list of IP addresses as aliases
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateInterface = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/network/interface/" + "Interface.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "int_name"             : ""            // (string) – user name for the interface
        , "int_interface"        : ""            // (string) – name of the physical interface
        , "int_ipv4address"      : ""            // (string) – main IPv4 address
        , "int_v4netmaskbit"     : ""            // (string) – number of bits for netmask (1..32)
        , "int_ipv6address"      : ""            // (string) – main IPv6 address
        , "int_v6netmaskbit"     : ""            // (string) – number of bits for netmask [0, 48, 60, 64, 80, 96]
        , "int_dhcp"             : true          // (boolean) – enable DHCP
        , "int_ipv6auto"         : true          // (boolean) – enable auto IPv6
        , "int_options"          : ""            // (string) – extra options to ifconfig(8)
        , "int_aliases"          : ""            // (list(string)) – list of IP addresses as aliases
      }    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteInterface = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/network/interface/" + "Interface.id" + "/?format=json"
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


// Network - VLAN
exports.getVlans = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/network/vlan/?format=json"
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

exports.addVlan = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/network/vlan/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "vlan_pint"          : ""    // (string) – physical interface
        , "vlan_vint"          : ""    // (string) – virtual interface name, vlanX
        , "vlan_description"   : ""    // (string) – user description
        , "vlan_tag"           : 12    // (integer) – vlan tag number
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateVlan = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/network/vlan/" + "Vlan.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "vlan_pint"          : ""    // (string) – physical interface
        , "vlan_vint"          : ""    // (string) – virtual interface name, vlanX
        , "vlan_description"   : ""    // (string) – user description
        , "vlan_tag"           : 12    // (integer) – vlan tag number
      }  
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteVlan = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/network/vlan/" + "Vlan.id" + "/?format=json"
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

// Network - LAGG
exports.getLaggs = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/network/lagg/?format=json"
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

exports.addLagg = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/network/lagg/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "lagg_interfaces"    : ""            // (list(string)) – list of physical interface names
        , "lagg_protocol"      : ""            // (string) – failover, fec, lacp, loadbalance, roundrobin, none
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteLagg = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/network/lagg/" + "Lagg.id" + "/?format=json"
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

// Network - Static Route
exports.getStaticroutes = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/network/staticroute/?format=json"
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

exports.addStaticroute = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/network/staticroute/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "sr_gateway"          : ""    // (string) – address of gateway
        , "sr_destination"      : ""    // (string) – network cidr
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateStaticroute = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/network/staticroute/" + "Staticroute.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "sr_gateway"          : ""    // (string) – address of gateway
        , "sr_destination"      : ""    // (string) – network cidr
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteStaticroute = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/network/staticroute/" + "Staticroute.id" + "/?format=json"
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
