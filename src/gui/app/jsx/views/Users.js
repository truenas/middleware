/** @jsx React.DOM */

// Users and Groups
// ================
// View showing all users and groups.

"use strict";


var React  = require("react");
var Viewer = require("../components/Viewer");

var _ = require("lodash");

// Twitter Bootstrap React components
var TWBS = require("react-bootstrap");

// Dummy data from API call on relatively unmolested system
// TODO: Update to use data from Flux store
var inputData  = require("../../fakedata/accounts.json");
var formatData = require("../../middleware-keys/accounts-display.json")[0];

var UsersEditor = React.createClass({
    render: function() {
      var innerstuff = [];

      // Create line items for editor form
      var createForm = function( item ) {
        var createField = function( inputValue ) {
          switch ( typeof inputValue ){
            case "boolean":
              return ( inputValue ? "Yes" : "No" );
            default:
              return ( inputValue );
          }
        };

        innerstuff.push(
          <span>
            <dt><b>{ this.props.formatData.dataKeys[ item ]["name"] }</b></dt>
            <dd style={{"text-overflow" : "ellipsis" }}>{ createField( this.props.inputData[ item ] ) }</dd>
            <dd>Robots are awesome</dd>
            <br />
          </span>
        );
      }.bind(this);

      _.chain( this.props.formatData.dataKeys)
       .keys()
       .forEach( createForm );

      return (
        <div>
          <h2>{ this.props.formatData.dataKeys[ this.props.formatData["primaryKey"] ]["name"] }</h2>
          <dl>
            { innerstuff }
          </dl>
        </div>
      );
    }
});

var Users = React.createClass({
    render: function() {
    return (
      <div>
        <h2>Cool people</h2>
        <Viewer header     = { "User Accounts" }
                editor     = { UsersEditor }
                inputData  = { inputData }
                formatData = { formatData } >
        </Viewer>
      </div>
    );
  }
});

module.exports = Users;