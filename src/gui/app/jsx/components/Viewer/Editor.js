/** @jsx React.DOM */

"use strict";

var _     = require("lodash");
var React = require("react");

var Editor = React.createClass({
   propTypes: {
      itemData     : React.PropTypes.object.isRequired
    , inputData    : React.PropTypes.array.isRequired
    , formatData   : React.PropTypes.object.isRequired
  }
  , getInitialState: function() {
      return {
        targetItem: this.changeTargetItem( this.props.params )
      };
    }
  , componentWillReceiveProps: function( nextProps ) {
      // TODO: Optimize based on changing props. Might need a shouldComponentUpdate.
      this.setState({
        targetItem: this.changeTargetItem( nextProps.params )
      });
    }
  , changeTargetItem: function( params ) {
      return _.find( this.props.inputData, function( item ) {
          // Returns the first object from the input array whose selectionKey matches
          // the current route's dynamic portion. For instance, /accounts/users/root
          // with bsdusr_usrname as the selectionKey would match the first object
          // in inputData whose username === "root"
          return params[ this.props.itemData["param"] ] === item[ this.props.formatData["selectionKey"] ];
        }.bind(this)
      );
    }
  , render: function() {
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


        return (
          <span key={ item["name"] }>
            <dt><b>{ item["name"] }</b></dt>
            <dd>{ createField( this.state.targetItem[ item["key"] ] ) }</dd>
            <br />
          </span>
        );
      }.bind(this);

      return (
        <div>
          <h2>{ this.state.targetItem[ this.props.formatData["primaryKey"] ] }</h2>
          <dl>
            { this.props.formatData.dataKeys.map( createForm ) }
          </dl>
        </div>
      );
    }
});

module.exports = Editor;