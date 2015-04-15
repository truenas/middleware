// INPUT HELPER MIXIN
// ==================
// Provides utility functions for generating common parts of input fields and
// maintaining proper local and remote state.

"use strict";

var _ = require("lodash");
var React = require("react");

module.exports = {

    // Takes an array and turns it into an array of options suitable for use
    // in a select box or multi-select box.
    generateOptionsList: function (options, selectionKey, displayKey) {
      var optionList = [];

      _.forEach(options, function( opt ) {
        var element = ( <option value = { opt[ selectionKey ] }
                                label = { opt[ displayKey ? displayKey: selectionKey ] } />);
        optionList.push(element);
      }, this );

      return optionList;
    }

    // Check if a given attribute is mutable according to the given data keys.
    // This is a PITA because this information is buried in an object in an
    // array in a prop, which cannot be helped.
  , isMutable: function (attribute, dataKeys) {
      return (_.find(dataKeys, function (dataKey) {
        return (dataKey.key === attribute);
      }, this).mutable);
    }

    // Returns an object containin the mutable fields from the item in nextProps.
    // A malformed nextProps will result in an empty array.
  , removeReadOnlyFields: function(item, keys) {
      var outgoingItem = {};
      // Used to put all the old fields into the new object, unless they're immutable
      outgoingItem = _.pick( item, function (value, key) {
        var keyContent = _.find(keys, function(checkKey){
          return (checkKey.key === key);
        }, this);
        if (keyContent) {
          return keyContent["mutable"];
        } else {
          // Do not accept unknown properties from the Middleware.
          // TODO: If we want to accept arbitrary properies, we will need more
          // sophisticated handling here.
          return false;
        }
      }, this  );
      return outgoingItem;
    }

    // Remote state is set at load time and reset upon successful changes. This
    // is used to highlight and submit only genuinely changed values.
  , setRemoteState: function ( incomingProps ) {
      var dataKeys = incomingProps.viewData["format"]["dataKeys"];
      var nextRemoteState = this.removeReadOnlyFields(incomingProps.item, dataKeys);

      if (_.isEmpty(nextRemoteState)) {
        console.warn("Remote State could not be created! Check the incoming props:");
        console.warn(incomingProps);
      }

      // TODO: What exactly should be returned if setting the remote state is
      // going to fail?
      return nextRemoteState;
    }

    // Deals with input from different kinds of input fields.
    // TODO: Extend with other input fields and refine existing ones as necessary.
  , processFormInput: function( event, dataKey ) {
        var inputValue;

        switch ( event.target.type ) {

          case "checkbox" :
            inputValue = event.target.checked;
            break;

          case "select":
          case "text":
          case "textarea":
          default:
            inputValue = this.parseInputType( event.target.value, dataKey );
            break;
        }

        return inputValue;
    }

    // Only differentiates numbers and strings for now.
  , parseInputType: function( input, dataKey ) {
      var output;

      switch ( dataKey.type ) {
        case "string":
          output = input;
          break;

        case "integer":
        case "number":
          output = _.parseInt( input );
          break;

        default:
          output = input;
          break;
      }

      return output;
    }

    // Requires that locallyModifiedValues be used to store changes made by the user
    // and mixedValues be used to store the data for display. remoteState must be the
    // last item receieved from the middleware, as it will be used for comparison.
    // See UserItem for typical usage.
    // This is specifically for edit views, not add entity views.
  , editHandleValueChange: function( key, event ) {
      var newLocallyModified = this.state.locallyModifiedValues;

      var dataKey = _.find( this.state.dataKeys, function ( dataKey ) {
        return ( dataKey.key === key );
      }, this );

      var inputValue = this.processFormInput( event, dataKey );

      // We don't want to submit non-changed data to the middleware, and it's
      // easy for data to appear "changed", even if it's the same. Here, we
      // check to make sure that the input value we've just receieved isn't the
      // same as what the last payload from the middleware shows as the value
      // for the same key. If it is, we `delete` the key from our temp object
      // and update state.
      if ( _.isEqual( this.state.remoteState[ key ], inputValue ) ) {
        delete newLocallyModified[ key ];
      } else {
        newLocallyModified[ key ] = inputValue;
      }

      // mixedValues functions as a clone of the original item passed down in
      // props, and is modified with the values that have been changed by the
      // user. This allows the display components to have access to the
      // "canonically" correct item, merged with the un-changed values.
      this.setState({
          locallyModifiedValues : newLocallyModified
        , mixedValues           : _.assign( _.cloneDeep( this.props.item ), newLocallyModified )
      });
    }

  , submissionRedirect: function( valuesToSend ) {
      var routing = this.props.viewData.routing;
      var params = {};
      var newEntityPath;

      if ( valuesToSend[ this.props.viewData.format[ "primaryKey" ] ] ) {
        newEntityPath = valuesToSend[ this.props.viewData.format[ "primaryKey" ] ];
        params[ routing[ "param" ] ] = newEntityPath;
        this.context.router.transitionTo( routing[ "route" ], params );
      } else {
        this.props.handleViewChange( "view" );
      }
    }
};
