// API Utility Functions
"use strict";

var request = require("request");
var _       = require("lodash");

var defaultConfig = {
    user : "root"
  , pass : "meh"
  , url  : "http://192.168.1.251"
};

// Accounts
// Users 
exports.getUsers = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/account/users/?format=json"
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


exports.addUser = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/account/users/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "bsdusr_username"           : "myuser"
        , "bsdusr_full_name"          : "haha"
        , "bsdusr_password"           : "psw.123"
        , "bsdusr_uid"                : 1111
        , "bsdusr_group"              : 16
        , "bsdusr_creategroup"        : true
        , "bsdusr_mode"               : "/nonexistent"   //unix mode to set the homedir
        , "bsdusr_shell"              : "/bin/csh" 
        , "bsdusr_password_disabled"  : false
        , "bsdusr_locked"             : false
        , "bsdusr_sudo"               : false
        , "bsdusr_sshpubkey"          : ""          //SSH authorized keys file content
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateUser = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/account/users/" + "user.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "bsdusr_username"           : "myuser"
        , "bsdusr_full_name"          : "haha"
        , "bsdusr_password"           : "psw.123"
        , "bsdusr_uid"                : 1111
        , "bsdusr_group"              : 16
        , "bsdusr_creategroup"        : true
        , "bsdusr_mode"               : "/nonexistent"   //unix mode to set the homedir
        , "bsdusr_shell"              : "/bin/csh" 
        , "bsdusr_password_disabled"  : false
        , "bsdusr_locked"             : false
        , "bsdusr_sudo"               : false
        , "bsdusr_sshpubkey"          : ""          //SSH authorized keys file content
      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteUser = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/account/users/" + "user.id" + "/?format=json"
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


//Change password skiped

exports.getUserGroups = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/account/users/" + "user.id" + "/groups/?format=json"
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

exports.setUserGroups = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/account/users/" + "user.id" + "/groups/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: [
          "wheel"
        , "ftp"
      ]  
    }, function( error, response, body ) {
      return response;
    }
  );
};


// Groups

exports.getGroups = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/account/groups/?format=json"
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

exports.addGroup = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/account/groups/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "bsdgrp_gid"    : 123
        , "bsdgrp_group"  : "group_name"
        , "bsdgrp_sudo"   : false

      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.updateGroup = function( options ) {
  request(
    { method : "PUT"
    , uri    : defaultConfig.url + "/api/v1.0/account/groups/" + "group.id" + "/?format=json"
    , json   : true
    , auth: {
          user   : "root"
        , pass   : "meh"
      }
    , data: {
          "bsdgrp_group"  : "group_name"
        , "bsdgrp_sudo"   : false

      }
    
    }, function( error, response, body ) {
      return response;
    }
  );
};

exports.deleteGroup = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/account/groups/" + "user.id" + "/?format=json"
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








