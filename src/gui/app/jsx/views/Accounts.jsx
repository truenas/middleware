// Users and Groups
// ================
// View showing all users and groups.

"use strict";

import React from "react";

import { RouteHandler } from "react-router";

import routerShim from "../components/mixins/routerShim";

import SectionNav from "../components/SectionNav";

var sections = [ { route : "users"
                 , display : "Users"
                 }
               , { route : "groups"
                 , display : "Groups"
                 } ];

const Accounts = React.createClass({

  displayName: "Accounts"

  ,  mixins: [ routerShim ]

  , componentDidMount: function () {
      this.calculateDefaultRoute( "accounts", "users", "endsWith" );
    }

  , componentWillUpdate: function ( prevProps, prevState ) {
      this.calculateDefaultRoute( "accounts", "users", "endsWith" );
    }

  , render: function () {
      return (
        <main>
          <SectionNav views = { sections } />
          <RouteHandler />
        </main>
      );
    }
});

export default Accounts;
