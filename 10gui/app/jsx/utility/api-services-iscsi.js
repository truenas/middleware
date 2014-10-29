// API Utility Functions
"use strict";

var request = require("request");
var _       = require("lodash");

var defaultConfig = {
    user : "root"
  , pass : "meh"
  , url  : "http://192.168.1.251"
};


// Services - iSCSI
exports.getIscsiconfiguration = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/iscsi/globalconfiguration/?format=json"
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


exports.updateIscsiconfiguration = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/iscsi/globalconfiguration/?format=json" 
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
		 "iscsi_basename" 				: ""		// (string) – base name (e.g. iqn.2007-09.jp.ne.peach.istgt, see RFC 3720 and 3721 for details)
		, "iscsi_discoveryauthmethod" 	: ""		// (string) – None, Auto, CHAP, CHAP Mutual
		, "iscsi_discoveryauthgroup" 	: ""		// (string) – id of auth group
       }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.getExtents = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/services/iscsi/extent/?format=json"
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


exports.addExtent = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/services/iscsi/extent/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
		  "iscsi_target_extent_name"           	: ""		// (string) – identifier of the extent
		, "iscsi_target_extent_type"           	: ""		// (string) – File, Device, ZFS Volume
		, "iscsi_target_extent_path"           	: ""		// (string) – path to the extent
		, "iscsi_target_extent_filesize"        : ""  		// (string) – size of extent, 0 means auto, a raw number is bytes, or suffix with KB, MB, TB for convenience
		, "iscsi_target_extent_insecure_tpc"    : true		// (boolean) – allow initiators to xcopy without authenticating to foreign targets
		, "iscsi_target_extent_comment"         : ""		// (string) – user description
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateExtent = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/services/iscsi/extent/" + "extent.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
		  "iscsi_target_extent_name"           	: ""		// (string) – identifier of the extent
		, "iscsi_target_extent_type"           	: ""		// (string) – File, Device, ZFS Volume
		, "iscsi_target_extent_path"           	: ""		// (string) – path to the extent
		, "iscsi_target_extent_filesize"        : ""  		// (string) – size of extent, 0 means auto, a raw number is bytes, or suffix with KB, MB, TB for convenience
		, "iscsi_target_extent_insecure_tpc"    : true		// (boolean) – allow initiators to xcopy without authenticating to foreign targets
		, "iscsi_target_extent_comment"         : ""		// (string) – user description
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteExtent = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/services/iscsi/extent/" + "extent.id" + "/?format=json"
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
