// API Utility Functions
"use strict";

var request = require("request");
var _       = require("lodash");

var defaultConfig = {
    user : "root"
  , pass : "meh"
  , url  : "http://192.168.1.251"
};


// Directory Service
// Active Directory
exports.getActiveDirectorySettings = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/activedirectory/?format=json"
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

exports.updateActiveDirectorySettings = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/activedirectory/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "ad_enable"              : "true/on"  // (string) – enable active directory // might be boolean, value needs to be guessed
        , "ad_certfile"            : ""         // (string) – ssl certificate
        , "ad_ssl"                 : "off"      // (string) – encryption mode (on/off/start_tls)
        , "ad_domainname"          : ""         // (string) – domain name
        , "ad_netbiosname"         : ""         // (string) – system hostname
        , "ad_bindpw"              : ""         // (string) – domain account password
        , "ad_dcname"              : ""         // (string) – hostname of the domain controller to use
        , "ad_gcname"              : ""         // (string) – hostname of the global catalog server to use
        , "ad_keytab"              : ""         // (string) – kerberos keytab file
        , "ad_use_keytab"          : false      // (boolean) – use keytab
        , "ad_krbname"             : ""         // (string) – hostname of the kerberos server to use
        , "ad_verbose_logging"     : false      // (boolean) – verbose logging
        , "ad_unix_extensions"     : false      // (boolean) – unix extensions
        , "ad_allow_trusted_doms"  : false      // (boolean) – allow Trusted Domains
        , "ad_use_default_domain"  : false      // (boolean) – use the default domain for users and groups
        , "ad_dns_timeout"         : 123        // (integer) – timeout for AD DNS queries
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

//LDAP
exports.getLdapSettings = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/ldap/?format=json"
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

exports.updateLdapSettings = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/ldap/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "ldap_hostname"          : ""     //(string) – name or IP address of the LDAP server
        , "ldap_basedn"            : ""     //(string) – default base Distinguished Name (DN) to use for searches
        , "ldap_anonbind"          : false  //(boolean) – allow anonymous binding
        //, "ldap_basedn"            : ""     //– distinguished name with which to bind to the directory server
        , "ldap_bindpw"            : ""     //(string) – credentials with which to bind
        , "ldap_binddn"            : ""     //(string) – distinguished name with which to bind to the directory server
        , "ldap_usersuffix"        : ""     //(string) – suffix that is used for users
        , "ldap_groupsuffix"       : ""     //(string) – suffix that is used for groups
        , "ldap_passwordsuffix"    : ""     //(string) – suffix that is used for password
        , "ldap_machinesuffix"     : ""     //(string) – suffix that is used for machines
        , "ldap_ssl"               : ""     //(string) – off, on, start_tls
        , "ldap_certfile"          : ""     //(string) – contents of your self signed certificate
        , "ldap_enable"            : false  //(boolean) – enable ldap directory service
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

//NIS
exports.getNisSettings = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/nis/?format=json"
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

exports.updateNisSettings = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/nis/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "nis_domain"        : ""    // (string) – nis domain name
        , "nis_servers"       : ""    // (string) – comma delimited list of NIS servers
        , "nis_secure_mode"   : true  // (boolean) – cause ypbind to run in secure mode
        , "nis_manycast"      : true  // (boolean) – cause ypbind to use “many-cast” instead of broadcast
        , "nis_enable"        : true  // (boolean) – enable nis
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

//NT4
exports.getNt4Settings = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/nt4/?format=json"
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

exports.updateNt4Settings = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/nt4/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {

      "nt4_dcname"        : ""   // (string) – hostname of the domain controller to use
    , "nt4_netbiosname"   : ""   // (string) – system hostname
    , "nt4_workgroup"     : ""   // (string) – workgroup or domain name in old format
    , "nt4_adminname"     : ""   // (string) – domain Administrator account name
    , "nt4_adminpw"       : ""   // (string) – domain Administrator account password
    , "nt4_enable"        : ""   // (string) – enable NT4

      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

//IDMAP
// AD Idmap
exports.getAdIdmap = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/ad/?format=json"
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

exports.setAdIdmap = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/ad/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_ad_schema_mode"    : ""    // (string) – defines the schema that idmap_ad should use when querying Active Directory (rfc2307, sfu, sfu20)
        , "idmap_ad_range_low"      : 1     // (integer) – range low
        , "idmap_ad_range_high"     : 123   // (integer) – range high
        , "idmap_ds_type"           : 2     // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"             : 33    // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateAdIdmap = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/ad/" + "AdImap.id" + "?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_ad_schema_mode"    : ""    // (string) – defines the schema that idmap_ad should use when querying Active Directory (rfc2307, sfu, sfu20)
        , "idmap_ad_range_low"      : 1     // (integer) – range low
        , "idmap_ad_range_high"     : 123   // (integer) – range high
        , "idmap_ds_type"           : 2     // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"             : 33    // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteAdIdmap = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/ad/" + "AdImap.id" + "?format=json"
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

// ADEX Idmap
exports.getAdexIdmap = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/adex/?format=json"
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

exports.setAdexIdmap = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/adex/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_adex_range_low"    : 1     // (integer) – range low
        , "idmap_adex_range_high"   : 11    // (integer) – range high
        , "idmap_ds_type"           : 2     // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"             : 123   // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateAdexIdmap = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/adex/" + "AdexImap.id" + "?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_adex_range_low"    : 1     // (integer) – range low
        , "idmap_adex_range_high"   : 11    // (integer) – range high
        , "idmap_ds_type"           : 2     // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"             : 123   // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteAdexIdmap = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/adex/" + "AdexImap.id" + "?format=json"
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

// Hash Idmap
exports.getHashIdmap = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/hash/?format=json"
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

exports.setHashIdmap = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/hash/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_hash_range_low"        : 1                     // (integer) – range low
        , "idmap_hash_range_high"       : 25                    // (integer) – range high
        , "idmap_hash_range_name_map"   : "/aaa/bbb/ccc"        // (string) – absolute path to the name mapping file
        , "idmap_ds_type"               : 1                     // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"                 : 111                   // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateHashIdmap = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/hash/" + "HashImap.id" + "?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_hash_range_low"        : 1                     // (integer) – range low
        , "idmap_hash_range_high"       : 25                    // (integer) – range high
        , "idmap_hash_range_name_map"   : "/aaa/bbb/ccc"        // (string) – absolute path to the name mapping file
        , "idmap_ds_type"               : 1                     // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"                 : 111                   // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteHashIdmap = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/hash/" + "HashImap.id" + "?format=json"
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

// LDAP Idmap
exports.getLdapIdmap = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/ldap/?format=json"
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

exports.setLdapIdmap = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/ldap/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_ldap_range_low"     : 1      // (integer) – range low
        , "idmap_ldap_range_high"    : 25     // (integer) – range high
        , "idmap_ldap_ldap_base_dn"  : "xyz"  // (string) – directory base suffix to use for SID/uid/gid
        , "idmap_ldap_ldap_user_dn"  : ""     // (string) – user DN to be used for authentication
        , "idmap_ldap_ldap_url"      : ""     // (string) – Specifies the LDAP server to use for SID/uid/gid map entries
        , "idmap_ds_type"            : 3      // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"              : 321    // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateLdapIdmap = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/ldap/" + "LdapImap.id" + "?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_ldap_range_low"     : 1      // (integer) – range low
        , "idmap_ldap_range_high"    : 25     // (integer) – range high
        , "idmap_ldap_ldap_base_dn"  : "xyz"  // (string) – directory base suffix to use for SID/uid/gid
        , "idmap_ldap_ldap_user_dn"  : ""     // (string) – user DN to be used for authentication
        , "idmap_ldap_ldap_url"      : ""     // (string) – Specifies the LDAP server to use for SID/uid/gid map entries
        , "idmap_ds_type"            : 3      // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"              : 321    // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteLdapIdmap = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/ldap/" + "LdapImap.id" + "?format=json"
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


// NSS Idmap
exports.getNssIdmap = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/nss/?format=json"
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

exports.setNssIdmap = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/nss/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_ad_range_low"    : 1          // (integer) – range low
        , "idmap_ad_range_high"   : 23         // (integer) – range high
        , "idmap_ds_type"         : 1          // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"           : 123        // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateNssIdmap = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/nss/" + "NssImap.id" + "?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_ad_range_low"    : 1          // (integer) – range low
        , "idmap_ad_range_high"   : 23         // (integer) – range high
        , "idmap_ds_type"         : 1          // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"           : 123        // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteNssIdmap = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/nss/" + "NssImap.id" + "?format=json"
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

// RFC2307 Idmap
exports.getRfc2307Idmap = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/rfc2307/?format=json"
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

exports.setRfc2307Idmap = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/rfc2307/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_rfc2307_range_low"          : 1         // (integer) – range low
        , "idmap_rfc2307_range_high"         : 25        // (integer) – range high
        , "idmap_rfc2307_bind_path_user"     : ""        // (string) – bind path where user objects “can be found in the LDAP server
        , "idmap_rfc2307_bind_path_group"    : ""        // (string) – bind path where group objects can be found in the LDAP server
        , "idmap_rfc2307_user_cn"            : true      // (boolean) – query cn attribute instead of uid attribute for the user name in LDAP
        , "idmap_rfc2307_cn_realm"           : ""        // (string) – append @realm to cn for groups
        , "idmap_rfc2307_ldap_server"        : ""        // (string) – type of LDAP server to use (ad)
        , "idmap_rfc2307_ldap_domain"        : ""        // (string) – allows to specify the domain where to access the Active Directory server
        , "idmap_rfc2307_ldap_url"           : ""        // (string) – ldap URL for accessing the LDAP server
        , "idmap_rfc2307_ldap_user_dn"       : ""        // (string) – user DN to be used for authentication
        , "idmap_rfc2307_ldap_realm"         : ""        // (string) – realm to use in the user and group names
        , "idmap_ds_type"                    : ""        // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"                      : ""        // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateRfc2307Idmap = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/rfc2307/" + "Rfc2307Imap.id" + "?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_rfc2307_range_low"          : 1         // (integer) – range low
        , "idmap_rfc2307_range_high"         : 25        // (integer) – range high
        , "idmap_rfc2307_bind_path_user"     : ""        // (string) – bind path where user objects “can be found in the LDAP server
        , "idmap_rfc2307_bind_path_group"    : ""        // (string) – bind path where group objects can be found in the LDAP server
        , "idmap_rfc2307_user_cn"            : true      // (boolean) – query cn attribute instead of uid attribute for the user name in LDAP
        , "idmap_rfc2307_cn_realm"           : ""        // (string) – append @realm to cn for groups
        , "idmap_rfc2307_ldap_server"        : ""        // (string) – type of LDAP server to use (ad)
        , "idmap_rfc2307_ldap_domain"        : ""        // (string) – allows to specify the domain where to access the Active Directory server
        , "idmap_rfc2307_ldap_url"           : ""        // (string) – ldap URL for accessing the LDAP server
        , "idmap_rfc2307_ldap_user_dn"       : ""        // (string) – user DN to be used for authentication
        , "idmap_rfc2307_ldap_realm"         : ""        // (string) – realm to use in the user and group names
        , "idmap_ds_type"                    : ""        // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"                      : ""        // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteRfc2307Idmap = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/rfc2307/" + "Rfc2307Imap.id" + "?format=json"
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


// TDB Idmap
exports.getTdbIdmap = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/tdb/?format=json"
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

exports.setTdbIdmap = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/tdb/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_tdb_range_low"   : 1  // (integer) – range low
        , "idmap_tdb_range_high"  : 2  // (integer) – range high
        , "idmap_ds_type"         : 3  // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"           : 4  // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateTdbIdmap = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/tdb/" + "TdbImap.id" + "?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_tdb_range_low"   : 1  // (integer) – range low
        , "idmap_tdb_range_high"  : 2  // (integer) – range high
        , "idmap_ds_type"         : 3  // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"           : 4  // (integer) – id of the directory service object
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteTdbIdmap = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/tdb/" + "TdbImap.id" + "?format=json"
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


// TDB2 Idmap
exports.getTdb2Idmap = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/tdb2/?format=json"
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

exports.setTdb2Idmap = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/tdb2/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_tdb_range_low"   : 1  // (integer) – range low
        , "idmap_tdb_range_high"  : 2  // (integer) – range high
        , "idmap_ds_type"         : 3  // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"           : 4  // (integer) – id of the directory service object
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateTdb2Idmap = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/tdb2/" + "Tdb2Imap.id" + "?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "idmap_tdb_range_low"   : 1  // (integer) – range low
        , "idmap_tdb_range_high"  : 2  // (integer) – range high
        , "idmap_ds_type"         : 3  // (integer) – type of the directory service (ad, ldap, nis, cifs)
        , "idmap_ds_id"           : 4  // (integer) – id of the directory service object
      }
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteTdb2Idmap = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/directoryservice/idmap/tdb2/" + "Tdb2Imap.id" + "?format=json"
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
