// INPUT HELPER MIXIN
// ==================
// Provides utility functions for generating common parts of input fields.

"use strict";

var _ = require("lodash");
var React = require("react");

module.exports = {

    // Takes an array and turns it into an array of options suitable for use
    // in a select box or multi-select box.
    generateOptionsList: function (optionArray) {
      var optionList = _.map(optionArray, function( opt ) {
        return ( <option>{opt.name}</option> );
      }, this);

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
          console.warn("Received an unknown property \"" + key + "\".");
          console.warn(this.props.item);
          return false;
        }
      }, this  );
      return outgoingItem;
    }

    // Deals with input from different kinds of input fields.
    // TODO: Extend with other input fields and refine existing ones as necessary.
  , processFormInput: function( event, dataKey ) {
        var inputValue;

        switch (event.target.type) {

          case "checkbox" :
            inputValue = event.target.checked;
            break;

          case "select":
          case "text":
          case "textarea":
          default:
            inputValue = this.parseInputType(event.target.value, dataKey);
            break;
        }

        return inputValue;
    }

    // Only differentiates numbers and strings for now.
  , parseInputType: function(input, dataKey) {
      var output;

      switch (dataKey.type) {
        case "string":
          output = input;
          break;

        case "integer":
        case "number":
          output = _.parseInt(input);
          break;

        default:
          output = input;
          break;
      }

      return output;
    }
};
