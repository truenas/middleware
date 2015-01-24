/** @jsx React.DOM */

"use strict";

var _     = require("lodash");
var React = require("react");

var Editor = React.createClass({

    propTypes: {
        viewData  : React.PropTypes.object.isRequired
      , inputData : React.PropTypes.any.isRequired
      , ItemView  : React.PropTypes.any.isRequired // FIXME: React 0.12 has better propTypes
      , EditView  : React.PropTypes.any            // FIXME: React 0.12 has better propTypes
      , params    : React.PropTypes.any // Provided as part of router's activeRouteHandler
    }

  , getInitialState: function() {
      return {
          targetItem  : this.changeTargetItem( this.props.inputData, this.props.params )
        , currentMode : "view"
      };
    }

  , componentWillReceiveProps: function( nextProps ) {
      // TODO: Optimize based on changing props. Might need a shouldComponentUpdate.
      var nextTargetItem = this.changeTargetItem( nextProps.inputData, nextProps.params );

      this.setState({
          targetItem  : nextTargetItem
        , currentMode : ( nextTargetItem[ this.props.viewData.format["selectionKey"] ] !== this.state.targetItem[ this.props.viewData.format["selectionKey"] ] ? "view" : this.state.currentMode )
      });
    }

  , changeTargetItem: function( inputData, params ) {
      return _.find( inputData, function( item ) {
          // Returns the first object from the input array whose selectionKey matches
          // the current route's dynamic portion. For instance, /accounts/users/root
          // with bsdusr_usrname as the selectionKey would match the first object
          // in inputData whose username === "root"

          return params[ this.props.viewData.routing["param"] ] === item[ this.props.viewData.format["selectionKey"] ];

        }.bind(this)
      );
    }

  , handleViewChange: function ( nextMode, event ) {
      this.setState({ currentMode: nextMode });
    }

  , render: function() {
      var displayComponent;

      switch ( this.state.currentMode ) {

        default:
        case "view":
          displayComponent = this.props.ItemView;
          break;

        case "edit":
          displayComponent = this.props.EditView;
          break;

      }

      return (
        <displayComponent handleViewChange = { this.handleViewChange }
                          item             = { this.state.targetItem }
                          formatData       = { this.props.viewData.format } />
      );
    }

});

module.exports = Editor;
