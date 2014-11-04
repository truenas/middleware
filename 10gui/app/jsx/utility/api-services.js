// API Utility Functions
"use strict";

var request = require("request");
var _       = require("lodash");

var defaultConfig = {
    user : "root"
  , pass : "meh"
  , url  : "http://192.168.1.251"
};


// Services
exports.getServices = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/services/?format=json"
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

exports.updateService = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/services" + "service.id" + "/?format=json" //PUT /api/v1.0/services/services/(int:id|string:srv_service)/
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
    	  "srv_service"                : ""  		//(string) – name of the service
    	, "srv_enable"                 :  true 	// (boolean) – service enable

      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};


exports.getAfp = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/afp/?format=json"
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


exports.updateAfp = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/afp/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
    	  "afp_srv_guest_user"                 : ""		// (string) – guest account
    	, "afp_srv_guest"              		   : true		// (boolean) – allow guest access
    	, "afp_srv_connections_limit"          : 123		// (integer) – maximum number of connections permitted
    	, "afp_srv_homedir"                    : ""		// (string) – path to home directory
    	, "afp_srv_homedir_enable"             : true		// (boolean) – enable to home directory feature
    	, "afp_srv_dbpath"                 	   : ""		// (string) – database information to be stored in path
    	, "afp_srv_global_aux"                 : ""		// (string) – auxiliary parameters in Global section
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};


exports.getCifs = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/cifs/?format=json"
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


exports.updateCifs = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/cifs/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {

    	 "cifs_srv_authmodel"                : ""		// (string) – user, share
    	, "cifs_srv_netbiosname"             : ""	 	// (string) – netbios name
    	, "cifs_srv_workgroup"               : ""	 	// (string) – workgroup
    	, "cifs_srv_description"             : ""	 	// (string) – server description
    	, "cifs_srv_doscharset"              : ""	 	// (string) – CP437, CP850, CP852, CP866, CP932, CP949, CP950, CP1026, CP1251, ASCII
    	, "cifs_srv_unixcharset"             : ""	 	// (string) – UTF-8, iso-8859-1, iso-8859-15, gb2312, EUC-JP, ASCII
    	, "cifs_srv_loglevel"                : ""	 	// (string) – 1, 2, 3, 10
    	, "cifs_srv_localmaster"             : true	 	// (boolean) – local master
    	, "cifs_srv_timeserver"              : true	 	// (boolean) – time server for domain
    	, "cifs_srv_guest"                   : ""	 	// (string) – guest account
    	, "cifs_srv_filemask"                : ""	 	// (string) – file mask
    	, "cifs_srv_dirmask"                 : ""	 	// (string) – directory mask
    	, "cifs_srv_nullpw"                  : true	 	// (boolean) – allow empty password
    	, "cifs_srv_allow_execute_always"    : true	 	// (boolean) – controls the behaviour of smbd(8) when receiving a protocol request of “open for execution”
    	, "cifs_srv_max_protocol"            : ""	 	// (string) – highest protocol version that will be supported by the server
    	, "cifs_srv_min_protocol"            : ""	 	// (string) – lowest protocol version that will be supported by the server
    	, "cifs_srv_syslog"                  : true	 	// (boolean) – use syslog
    	, "cifs_srv_smb_options"             : ""	 	// (string) – auxiliary parameters added to [global] section
    	, "cifs_srv_unixext"                 : true	 	// (boolean) – unix extensions
    	, "cifs_srv_obey_pam_restrictions"   : true	 	// (boolean) – obey pam restrictions
    	, "cifs_srv_domain_logons"           : true	 	// (boolean) – domains logons
    	, "cifs_srv_aio_enable"              : true		// (boolean) – enable aio
    	, "cifs_srv_aio_rs"                  : 122		// (integer) – minimum aio read size
    	, "cifs_srv_aio_ws"                  : 123		// (integer) – minimum aio write size
    	, "cifs_srv_zeroconf"                : 124		// (boolean) – zeroconf share discovery
    	, "cifs_srv_hostlookup"              : 125		// (boolean) – hostname lookups

      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.getDomaincontroller = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/domaincontroller/?format=json"
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


exports.updateDomaincontroller = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/domaincontroller/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
    	  "dc_realm"  			: ""			// (string) – Realm Name, eg EXAMPLE.ORG
    	, "dc_domain"  			: ""			// (string) – Domain Name in old format, eg EXAMPLE
    	, "dc_role"  			: ""			// (string) – Server Role (dc)
    	, "dc_dns_backend"  	: ""			// (string) – DNS Backend (SAMBA_INTERNAL/BIND9_FLATFILE/BIND9_DLZ/NONE)
    	, "dc_dns_forwarder"  	: ""			// (string) – DNS Forwarder IP Address
    	, "dc_forest_level"  	: ""			// (string) – Domain and Forest Level (2000/2003/2008/2008_R2)
    	, "dc_passwd"  			: ""			// (string) – Administrator Password

      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.getDynamicdns = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/dynamicdns/?format=json"
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


exports.updateDynamicdns = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/dynamicdns/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {

    	  "ddns_ipserver" 			: ""		// (string) – client IP is detected by this calling url
    	, "ddns_provider" 			: ""		// (string) – dyndns@dyndns.org, default@freedns.afraid.org, default@zoneedit.com, default@no-ip.com, default@easydns.com, dyndns@3322.org, default@sitelutions.com, default@dnsomatic.com, ipv6tb@he.net, default@tzo.com, default@dynsip.org, default@dhis.org, default@majimoto.net, default@zerigo.com
    	, "ddns_domain" 			: ""		// (string) – host name alias
    	, "ddns_username" 			: ""		// (string) – username
    	, "ddns_password" 			: ""		// (string) – password
    	, "ddns_updateperiod" 		: ""		// (string) – time in seconds
    	, "ddns_fupdateperiod" 		: ""		// (string) – forced update period
    	, "ddns_options" 			: ""		// (string) – auxiliary parameters to global settings in inadyn-mt.conf
       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.getFtp = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/ftp/?format=json"
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


exports.updateFtp = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/ftp/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
    	  "ftp_port" 									: 21		// (integer) – port to bind FTP server
    	, "ftp_clients" 								: 10		// (integer) – maximum number of simultaneous clients
    	, "ftp_ipconnections" 							: 5			// (integer) – maximum number of connections per IP address
    	, "ftp_loginattempt" 							: 5			// (integer) – maximum number of allowed password attempts before disconnection
    	, "ftp_timeout" 								: 30		// (integer) – maximum idle time in seconds
    	, "ftp_rootlogin" 								: true		// (boolean) – allow root login
    	, "ftp_onlyanonymous" 							: true		// (boolean) – allow anonymous login
    	, "ftp_anonpath" 								: ""		// (string) – path for anonymous login
    	, "ftp_onlylocal" 								: true		// (boolean) – allow only local user login
    	, "ftp_banner" 									: ""		// (string) – message which will be displayed to the user when they initially login
    	, "ftp_filemask" 								: ""		// (string) – file creation mask
    	, "ftp_dirmask" 								: ""		// (string) – directory creation mask
    	, "ftp_fxp" 									: true		// (boolean) – enable fxp
    	, "ftp_resume" 									: true		// (boolean) – allow transfer resumption
    	, "ftp_defaultroot" 							: true		// (boolean) – only allow access to user home unless member of wheel
    	, "ftp_ident" 									: true		// (boolean) – require IDENT authentication
    	, "ftp_reversedns" 								: true		// (boolean) – perform reverse dns lookup
    	, "ftp_masqaddress" 							: ""		// (string) – causes the server to display the network information for the specified address to the client
    	, "ftp_passiveportsmin" 						: 1111		// (integer) – the minimum port to allocate for PASV style data connections
    	, "ftp_passiveportsmax" 						: 2222		// (integer) – the maximum port to allocate for PASV style data connections
    	, "ftp_localuserbw" 							: 100		// (integer) – local user upload bandwidth in KB/s
    	, "ftp_localuserdlbw" 							: 100		// (integer) – local user download bandwidth in KB/s
    	, "ftp_anonuserbw" 								: 10		// (integer) – anonymous user upload bandwidth in KB/s
    	, "ftp_anonuserdlbw" 							: 10		// (integer) – anonymous user download bandwidth in KB/s
    	, "ftp_tls" 									: true		// (boolean) – enable TLS
    	, "ftp_tls_opt_allow_client_renegotiations" 	: true		// (boolean) – allow client renegotiations
    	, "ftp_tls_opt_allow_dot_login" 				: true		// (boolean) – allow dot login
    	, "ftp_tls_opt_allow_per_user" 					: true		// (boolean) – allow per user options
    	, "ftp_tls_opt_common_name_required" 			: true		// (boolean) – certificate common name is required
    	, "ftp_tls_opt_dns_name_required" 				: true		// (boolean) – dns name certificate required
    	, "ftp_tls_opt_enable_diags" 					: true		// (boolean) – enable diags
    	, "ftp_tls_opt_export_cert_data" 				: true		// (boolean) – export certificate data
    	, "ftp_tls_opt_ip_address_required" 			: true		// (boolean) – ip address required
    	, "ftp_tls_opt_no_cert_request" 				: true		// (boolean) – no certificate request
    	, "ftp_tls_opt_no_empty_fragments" 				: true		// (boolean) – no empty fragments
    	, "ftp_tls_opt_no_session_reuse_required" 		: true		// (boolean) – no session reuse requird
    	, "ftp_tls_opt_stdenvvars" 						: true		// (boolean) – standard environment variables
    	, "ftp_tls_opt_use_implicit_ssl" 				: true		// (boolean) – use implicit SSL
    	, "ftp_ssltls_certfile" 						: ""		// (string) – certificate and private key
    	, "ftp_options" 								: ""		// (string) – these parameters are added to proftpd.conf
       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};


exports.getLldp = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/lldp/?format=json"
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


exports.updateLldp = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/lldp/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
    	  "lldp_country" 	: ""	// (string) – two-letterISO 3166 country code
    	, "lldp_location" 	: ""	// (string) – physical location of the host
    	, "lldp_intdesc" 	: true	// (boolean) – save received info in interface description / alias
       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};


exports.getNfs = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/nfs/?format=json"
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


exports.updateNfs = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/nfs/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {

    	  "nfs_srv_servers" 					: ""		// (string) – how many servers to create
    	, "nfs_srv_allow_nonroot" 				: true		// (boolean) – allow non-root mount requests to be served.
    	, "nfs_srv_udp" 						: true		// (boolean) – serve UDP requests
    	, "nfs_srv_v4" 							: true		// (boolean) – enable NFS v4
    	, "nfs_srv_bindip" 						: ""		// (string) – IP addresses (separated by commas) to bind to for TCP and UDP requests
    	, "nfs_srv_mountd_port" 				: 123		// (integer) – force mountd to bind to the specified port
    	, "nfs_srv_rpcstatd_port" 				: 321		// (integer) – forces the rpc.statd daemon to bind to the specified port
    	, "nfs_srv_rpclockd_port" 				: 222		// (integer) – forces rpc.lockd the daemon to bind to the specified port

       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.getRsyncd = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/rsyncd/?format=json"
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


exports.updateRsyncd = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/rsyncd/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
      "rsyncd_port" 		: 873		// (integer) – alternate TCP port. Default is 873
    , "rsyncd_auxiliary" 	: ""		// (string) – parameters will be added to [global] settings in rsyncd.conf


       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};


exports.getRsyncmod = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/rsyncmod/?format=json"
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

exports.addRsyncmod = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/account/rsyncmod/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {

		 "rsyncmod_name"  				: ""		// (string) – module name
		, "rsyncmod_comment"  			: ""		// (string) – comment
		, "rsyncmod_path"  				: ""		// (string) – path to share
		, "rsyncmod_mode"  				: ""		// (string) – ro, wo, rw
		, "rsyncmod_maxconn"  			: 10		// (integer) – maximum number of simultaneous connections
		, "rsyncmod_user"  				: ""		// (string) – user name that file transfers to and from that module should take place
		, "rsyncmod_group"  			: ""		// (string) – group name that file transfers to and from that module should take place
		, "rsyncmod_hostsallow"			: ""		// (string) – comma, space, or tab delimited set of hosts which are permitted to access this module
		, "rsyncmod_hostsdeny" 			: ""		// (string) – comma, space, or tab delimited set of hosts which are NOT permitted to access this module
		, "rsyncmod_auxiliary" 			: ""		// (string) – parameters will be added to the module configuration in rsyncd.conf

      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};


exports.updateRsyncmod = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/rsyncmod/" + "rsyncmod.id" + "/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {

		 "rsyncmod_name"  				: ""		// (string) – module name
		, "rsyncmod_comment"  			: ""		// (string) – comment
		, "rsyncmod_path"  				: ""		// (string) – path to share
		, "rsyncmod_mode"  				: ""		// (string) – ro, wo, rw
		, "rsyncmod_maxconn"  			: 10		// (integer) – maximum number of simultaneous connections
		, "rsyncmod_user"  				: ""		// (string) – user name that file transfers to and from that module should take place
		, "rsyncmod_group"  			: ""		// (string) – group name that file transfers to and from that module should take place
		, "rsyncmod_hostsallow"			: ""		// (string) – comma, space, or tab delimited set of hosts which are permitted to access this module
		, "rsyncmod_hostsdeny" 			: ""		// (string) – comma, space, or tab delimited set of hosts which are NOT permitted to access this module
		, "rsyncmod_auxiliary" 			: ""		// (string) – parameters will be added to the module configuration in rsyncd.conf

      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteRsyncmod = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/services/rsyncmod/" + "rsyncmod.id" + "/?format=json" 
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

exports.getSmart = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/smart/?format=json"
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


exports.updateSmart = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/smart/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
		  "smart_interval"        : 30       // (integer) – interval between disk checks in minutes
		, "smart_powermode"       : ""       // (string) – never, sleep, standby, idle
		, "smart_difference"      : 5        // (integer) – report if the temperature had changed by at least N degrees Celsius since last report
		, "smart_informational"   : 3        // (integer) – report as informational if the temperature had changed by at least N degrees Celsius since last report
		, "smart_critical"        : 10       // (integer) – report as critical if the temperature had changed by at least N degrees Celsius since last report
		, "smart_email"           : ""		 // (string) – destination email address
       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.getSnmp = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/snmp/?format=json"
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


exports.updateSnmp = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/snmp/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
		  "snmp_location"  	   	: ""           	// (string) – location information, e.g. physical location of this system
		, "snmp_contact"    	: ""        	// (string) – contact information
		, "snmp_community"   	: ""  	        // (string) – in most cases, “public” is used here
		, "snmp_traps"        	: ""	        // (string) – send SNMP traps
		, "snmp_options"      	: ""          	// (string) – parameters will be added to /etc/snmpd.config
       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.getSsh = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/ssh/?format=json"
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


exports.updateSsh = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/ssh/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
		  "ssh_tcpport"                 : ""        	// (string) – alternate TCP port. Default is 22
		, "ssh_rootlogin"               : ""          	// (string) – Disabled: Root can only login via public key authentication; Enabled: Root login permitted with password
		, "ssh_passwordauth"            : ""           	// (string) – Allow Password Authentication
		, "ssh_tcpfwd"                  : ""       		// (string) – Allow TCP Port Forwarding
		, "ssh_compression"             : ""           	// (string) – Compress Connections
		, "ssh_privatekey"              : ""           	// (string) – RSA PRIVATE KEY in PEM format
		, "ssh_sftp_log_level"          : ""           	// (string) – QUIET, FATAL, ERROR, INFO, VERBOSE, DEBUG, DEBUG2, DEBUG3
		, "ssh_sftp_log_facility"       : ""           	// (string) – DAEMON, USER, AUTH, LOCAL0, LOCAL1, LOCAL2, LOCAL3, LOCAL4, LOCAL5, LOCAL6, LOCAL7
		, "ssh_options"                 : ""        	// (string) – extra options to /etc/ssh/sshd_config
       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.getTftp = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/tftp/?format=json"
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


exports.updateTftp = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/tftp/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
		  "tftp_directory"      : ""          // (string) – the directory containing the files you want to publish
		, "tftp_newfiles"       : true        // (boolean) – Allow New Files
		, "tftp_port"           : 21          // (integer) – port to listen to
		, "tftp_username"       : ""          // (string) – username which the service will run as
		, "tftp_umask"          : ""          // (string) – umask for newly created files
		, "tftp_options"        : ""          // (string) – extra command line options
       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};


exports.getUps = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/ups/?format=json"
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


exports.updateUps = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/ups/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
		  "ups_mode"            	: ""   		// (string) – master, slave
		, "ups_identifier"      	: ""   		// (string) – name is used to uniquely identify your UPS
		, "ups_remotehost"      	: ""   		// (string) – Remote Host
		, "ups_remoteport"      	: 12   		// (integer) – Remote Port
		, "ups_driver"          	: ""   		// (string) – see /usr/local/etc/nut/driver.list
		, "ups_port"            	: ""   		// (string) – path to serial or USB port where your UPS is connected
		, "ups_options"         	: ""   		// (string) – auxiliary parameters (ups.conf)
		, "ups_description"     	: ""   		// (string) – Description
		, "ups_shutdown"        	: ""   		// (string) – lowbatt, batt
		, "ups_shutdowntimer"   	: 30   		// (integer) – time in seconds until shutdown is initiated
		, "ups_monuser"         	: ""   		// (string) – Monitor User
		, "ups_monpwd"          	: ""   		// (string) – Monitor Password
		, "ups_extrausers"      	: ""   		// (string) – Extra users (upsd.users)
		, "ups_rmonitor"        	: true 		// (boolean) – Remote Monitor
		, "ups_emailnotify"     	: true 		// (boolean) – Send Email Status Updates
		, "ups_toemail"         	: ""   		// (string) – destination email address
		, "ups_subject"         	: ""   		// (string) – subject of the email. You can use the following: %d - Date; %h - Hostname
       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};