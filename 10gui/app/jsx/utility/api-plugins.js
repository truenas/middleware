// API Utility Functions
"use strict";

var request = require("request");
var _       = require("lodash");

var defaultConfig = {
    user : "root"
  , pass : "meh"
  , url  : "http://192.168.1.251"
};

// Plugins
exports.getPlugins = function( options ) {
  request(
    { method : "GET"
    , uri    : defaultConfig.url + "/api/v1.0/plugins/plugins/?format=json"
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

exports.startPlugin = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/plugins/plugins/" + "Plugin.id" + "/start/?format=json"
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

exports.stopPlugin = function( options ) {
  request(
    { method : "POST"
    , uri    : defaultConfig.url + "/api/v1.0/plugins/plugins/" + "Plugin.id" + "/stop/?format=json"
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

exports.deletePlugin = function( options ) {
  request(
    { method : "DELETE"
    , uri    : defaultConfig.url + "/api/v1.0/plugins/plugins/" + "Plugin.id" + "/?format=json"
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
