// SHELL
// This allows Grunt access to shell commands. A common use case is
// reinstalling packages and dependencies after a big change.

"use strict";

module.exports = function ( grunt ) {
  this.reloadPackages = {
    command: [ "npm install", "bower install" ].join( "&&" )
  };

  this.npmProduction = {
    command: "npm install --production"
  };
};
