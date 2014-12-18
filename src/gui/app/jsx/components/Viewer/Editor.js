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
      return (
        <this.props.ItemView item={ this.state.targetItem } />
      );
    }

});

module.exports = Editor;