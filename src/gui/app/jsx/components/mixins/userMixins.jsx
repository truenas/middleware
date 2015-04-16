// User Editing Mixins
// ===================
// Various things that are needed for just about any view that will be editing users.

"use strict";

var _ = require("lodash");

var ShellMiddleware = require("../../middleware/ShellMiddleware");

module.exports = {

    componentDidMount: function() {
      ShellMiddleware.requestAvailableShells( function( shells ) {
        var systemShells = _.map(shells, function( shell ){
          return ( { name : shell }
          );
        }, this);
        // Manually add nologin
        systemShells.push( { name: "/usr/sbin/nologin" } );
        this.setState({ shells: systemShells });
      }.bind( this ) );
    }

    // Converts an array of strings into an array of integers. Intended solely
    // for use when submitting groups lists to the middleware.
  , parseGroupsArray: function( groupsArray ) {
      var integerArray = [];

      integerArray = _.map( groupsArray, function( group ){
        return _.parseInt( group );
      }, this );

      return integerArray;
    }
};
