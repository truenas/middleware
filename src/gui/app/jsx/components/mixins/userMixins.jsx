// User Editing Mixins
// ===================
// Various things that are needed for just about any view that will be editing users.

"use strict";

import _ from "lodash";

import ShellMiddleware from "../../middleware/ShellMiddleware";

import UsersStore from "../../stores/UsersStore";
import UsersMiddleware from "../../middleware/UsersMiddleware";

module.exports = {

    componentDidMount: function () {
      ShellMiddleware.requestAvailableShells( function( shells ) {
        var systemShells = _.map(shells, function( shell ){
          return ( { name : shell }
          );
        }, this);
        // Manually add nologin
        systemShells.push( { name: "/usr/sbin/nologin" } );
        this.setState({ shells: systemShells });
      }.bind( this ) );

      UsersStore.addChangeListener(this.updateUsersInState);
    }

  , componentWillUnmount: function () {
      UsersStore.removeChangeListener(this.updateUsersInState);
    }

  , updateUsersInState: function () {
      var usersList = UsersStore.getAllUsers();
      this.setState( { usersList : usersList } );
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

  , deleteUser: function (){
        UsersMiddleware.deleteUser(this.props.item["id"], this.returnToViewerRoot() );
    }
};
