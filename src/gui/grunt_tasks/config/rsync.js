// RSYNC
// Rsync modified build files and application code to remote FreeNAS
// instance.

"use strict";

module.exports = function( grunt ) {
  this.options = { exclude: [ "app/source"
                            , "app/jsx"
                            ]
                 , recursive : true
                 , delete    : true
                 };

  this.freenas =
    { options : { ssh        : true
                , port       : "<%= freeNASConfig.sshPort %>"
                , privateKey : "<%= freeNASConfig.keyPath %>"
                , src        : [ "./package.json", "./app" ]
                , dest       : "root@<%= freeNASConfig.remoteHost %>" + ":" +
                               "<%= guiDirectory %>"
                }
    };
};
