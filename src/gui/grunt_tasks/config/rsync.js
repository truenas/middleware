// RSYNC
// Rsync modified build files and application code to remote FreeNAS
// instance.

"use strict";

module.exports = function( grunt ) {
  this.options = {
        exclude: [
          "app/source"
        ]
      , recursive : true
      , delete    : true
  };

  this.freenas = {
      options : {
          ssh        : true
        , port       : "<%= freenasConfig.sshPort %>"
        , privateKey : "<%= freenasConfig.keyPath %>"
        , src        : [ "./package.json", "./app" ]
        , dest       : "root@<%= freenasConfig.remoteHost %>:<%= freenasConfig.freeNASPath %>"
    }
  };
};