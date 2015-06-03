// Copyright (c) 2013, Peter Ruibal <ruibalp@gmail.com>

// Permission to use, copy, modify, and/or distribute this software for any
// purpose with or without fee is hereby granted, provided that the above
// copyright notice and this permission notice appear in all copies.

// THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
// REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
// AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
// INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
// LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
// OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
// PERFORMANCE OF THIS SOFTWARE.
//
// Generic Fuzzy Search TypeAhead React Component
// ===============================
// Taken (and Modified) from : https://github.com/fmoo/react-typeahead

"use strict";

import React from "react";
import fuzzy from "fuzzy";
import classNames from "classnames";
import TWBS from "react-bootstrap";
/**
 * PolyFills make me(The author Peter Ruibal) sad
 */
var KeyEvent = KeyEvent || {};
KeyEvent.DOM_VK_UP = KeyEvent.DOM_VK_UP || 38;
KeyEvent.DOM_VK_DOWN = KeyEvent.DOM_VK_DOWN || 40;
KeyEvent.DOM_VK_BACK_SPACE = KeyEvent.DOM_VK_BACK_SPACE || 8;
KeyEvent.DOM_VK_RETURN = KeyEvent.DOM_VK_RETURN || 13;
KeyEvent.DOM_VK_ENTER = KeyEvent.DOM_VK_ENTER || 14;
KeyEvent.DOM_VK_ESCAPE = KeyEvent.DOM_VK_ESCAPE || 27;
KeyEvent.DOM_VK_TAB = KeyEvent.DOM_VK_TAB || 9;

/**
 * A single option within the TypeaheadSelector
 */
var TypeaheadOption = React.createClass(

  { propTypes: { customClasses: React.PropTypes.object
               , customValue: React.PropTypes.string
               , onClick: React.PropTypes.func
               , children: React.PropTypes.string
               , hover: React.PropTypes.bool
    }

  , getDefaultProps: function ( ) {
      return { customClasses: {}
             , onClick: function ( event ) {
          event.preventDefault();
        }
      };
    }

  , getInitialState: function ( ) {
      return {};
    }

  , _onClick: function ( event ) {
      event.preventDefault();
      return this.props.onClick( event );
    }

  , _getClasses: function ( ) {
      var classes = {
        "typeahead-option": true
      };
      classes[this.props.customClasses.listAnchor] =
        !!this.props.customClasses.listAnchor;

      return classNames( classes );
    }

  , render: function ( ) {
      var classes = {};
      classes[this.props.customClasses.hover || "hover"] = !!this.props.hover;
      classes[this.props.customClasses.listItem] =
        !!this.props.customClasses.listItem;

      if ( this.props.customValue ) {
        classes[this.props.customClasses.customAdd] =
          !!this.props.customClasses.customAdd;
      }

      var classList = classNames( classes );

      return (
        <li className={ classList } onClick={ this._onClick }>
          <a href="javascript: void 0;"
             className={ this._getClasses() } ref="anchor">
            { this.props.children }
          </a>
        </li>
      );
    }
  }
);


/**
 * Container for the options rendered as part of the autocompletion process
 * of the typeahead
 */
var TypeaheadSelector = React.createClass(
  { propTypes: { options: React.PropTypes.array
               , customClasses: React.PropTypes.object
               , customValue: React.PropTypes.string
               , selectionIndex: React.PropTypes.number
               , onOptionSelected: React.PropTypes.func
    }

  , getDefaultProps: function ( ) {
      return { selectionIndex: null
             , customClasses: {}
             , customValue: null
             , onOptionSelected: function ( option ) { }
      };
    }

  , getInitialState: function ( ) {
      return { selectionIndex: this.props.selectionIndex
             , selection: this.getSelectionForIndex( this.props.selectionIndex )
      };
    }

  , setSelectionIndex: function ( index ) {
      this.setState({ selectionIndex: index
                    , selection: this.getSelectionForIndex( index )
      });
    }

  , getSelectionForIndex: function ( index ) {
      if ( index === null ) {
        return null;
      }
      if ( index === 0 && this.props.customValue !== null ) {
        return this.props.customValue;
      }

      if ( this.props.customValue !== null ) {
        index -= 1;
      }

      return this.props.options[index];
    }

  , _onClick: function ( result, event ) {
      return this.props.onOptionSelected( result, event );
    }

  , _nav: function ( delta ) {
      if ( !this.props.options && this.props.customValue === null ) {
        return;
      }
      var newIndex = this.state.selectionIndex === null ?
        ( delta === 1 ?
            0 : delta ) : this.state.selectionIndex + delta;
      var length = this.props.options.length;
      if ( this.props.customValue !== null ) {
        length += 1;
      }

      if ( newIndex < 0 ) {
        newIndex += length;
      } else if ( newIndex >= length ) {
        newIndex -= length;
      }

      var newSelection = this.getSelectionForIndex( newIndex );
      this.setState({ selectionIndex: newIndex
                    , selection: newSelection });
    }

  , navDown: function ( ) { this._nav( 1 ); }

  , navUp: function ( ) { this._nav( -1 ); }

  , render: function ( ) {
      var classes = { "typeahead-selector": true };
      classes[this.props.customClasses.results] =
        this.props.customClasses.results;
      var classList = classNames( classes );

      var results = [];
      // CustomValue should be added to top of results
      // list with different class name
      if ( this.props.customValue !== null ) {
        results.push(
          <TypeaheadOption ref={this.props.customValue}
                           key={this.props.customValue}
                           hover={this.state.selectionIndex === results.length}
                           customClasses={this.props.customClasses}
                           customValue={this.props.customValue}
                           onClick={
                             this._onClick.bind( this
                                               , this.props.customValue ) }>
            { this.props.customValue }
          </TypeaheadOption> );
      }

      this.props.options.forEach( function ( result, i ) {
        results.push(
          <TypeaheadOption
            ref={ result } key={ result }
            hover={ this.state.selectionIndex === results.length }
            customClasses={ this.props.customClasses }
            onClick={ this._onClick.bind( this, result ) }>
            { result }
          </TypeaheadOption>
        );
      }, this );

      return <ul className={classList}>{ results }</ul>;
    }

  }
);


/**
 * A "typeahead", an auto-completing text input
 *
 * Renders an text input that shows options nearby that you can use the
 * keyboard or mouse to select.  Requires CSS for MASSIVE DAMAGE.
 */
var FuzzyTypeAhead = React.createClass(

  { propTypes: { name              : React.PropTypes.string
               , customClasses     : React.PropTypes.object
               , maxVisible        : React.PropTypes.number
               , options           : React.PropTypes.array
               , allowCustomValues : React.PropTypes.number
               , defaultValue      : React.PropTypes.string
               , placeholder       : React.PropTypes.string
               , onOptionSelected  : React.PropTypes.func
               , onKeyDown         : React.PropTypes.func
               , filterOption      : React.PropTypes.func
               , onKeyPress        : React.PropTypes.func
    }

  , getDefaultProps: function ( ) {
      return { options           : []
             , customClasses     : {}
             , allowCustomValues : 0
             , defaultValue      : ""
             , placeholder       : ""
             , onOptionSelected  : function ( option ) {}
             , onKeyDown         : function ( event ) {}
             , filterOption      : null
             , onKeyPress        : function ( event ) {}
      };
    }

  , getInitialState: function ( ) {
      return { visible: this.getOptionsForValue( this.props.defaultValue
                                        , this.props.options )
               // ^^ The currently visible set of options
             , entryValue: this.props.defaultValue
               // ^^ This should be called something else, "entryValue"
             , selection: null
               // ^^ A valid typeahead value
      };
    }

  , getOptionsForValue: function ( value, options ) {
      var result;
      if ( this.props.filterOption ) {
        result = options.filter( ( function ( o ) {
          return this.props.filterOption( value, o ); }).bind( this ) );
      } else {
        result = fuzzy.filter( value, options ).map( function ( res ) {
          return res.string;
        });
      }
      if ( this.props.maxVisible ) {
        result = result.slice( 0, this.props.maxVisible );
      }
      return result;
    }

  , _hasCustomValue: function ( ) {
      if ( this.props.allowCustomValues > 0 &&
           this.state.entryValue.length >= this.props.allowCustomValues &&
           this.state.visible.indexOf( this.state.entryValue ) < 0 ) {
        return true;
      }
      return false;
    }

  , _getCustomValue: function ( ) {
      if ( this._hasCustomValue() ) {
        return this.state.entryValue;
      }
      return null;
    }

  , _renderIncrementalSearchResults: function ( ) {
    // Nothing has been entered into the textbox
    if ( !this.state.entryValue ) {
      return "";
    }

    // Something was just selected
    if ( this.state.selection ) {
      return "";
    }

    // There are no typeahead / autocomplete suggestions
    if ( !this.state.visible.length && !( this.props.allowCustomValues > 0 ) ) {
      return "";
    }

    // There is only one typeahead result and it matches the entryValue
    // (mathces in the sense that it exactly matches and not fuzzy! )
    // In this case we would not want the typeahead to show anymore!
    if ( this.state.visible.length === 1 &&
         this.state.visible[0] === this.state.entryValue ) {
      return "";
    }

    if ( this._hasCustomValue() ) {
      return (
        <TypeaheadSelector
          ref="sel" options={this.state.visible}
          customValue={this.state.entryValue}
          onOptionSelected={this._onOptionSelected}
          customClasses={this.props.customClasses} />
      );
    }

    return (
      <TypeaheadSelector
        ref="sel" options={ this.state.visible }
        onOptionSelected={ this._onOptionSelected }
        customClasses={this.props.customClasses} />
   );
  }

  , _onOptionSelected: function ( option, event ) {
      let nEntry = React.findDOMNode( this.refs.entry );
      nEntry.focus();
      nEntry.value = option;
      this.setState({ visible: this.getOptionsForValue( option
                                                      , this.props.options )
                    , selection: option
                    , entryValue: option });
      return this.props.onOptionSelected( option, event );
    }

  , _onTextEntryUpdated: function ( event ) {
      var value = event.target.value;
      this.setState({ visible    : this.getOptionsForValue( value
                                                          , this.props.options )
                    , selection  : null
                    , entryValue : value});
    }

  , _onEnter: function ( event ) {
      if ( !this.refs.sel.state.selection ) {
        return this.props.onKeyDown( event );
      }
      return this._onOptionSelected( this.refs.sel.state.selection, event );
    }

  , _onEscape: function ( ) {
      this.refs.sel.setSelectionIndex( null );
    }

  , _onTab: function ( event ) {
      var option = this.refs.sel.state.selection ?
        this.refs.sel.state.selection : ( this.state.visible.length > 0 ?
                                            this.state.visible[0] : null );

      if ( option === null && this._hasCustomValue() ) {
        option = this._getCustomValue();
      }

      if ( option !== null ) {
        return this._onOptionSelected( option, event );
      }
    }

  , eventMap: function ( event ) {
      var events = {};

      events[KeyEvent.DOM_VK_UP] = this.refs.sel.navUp;
      events[KeyEvent.DOM_VK_DOWN] = this.refs.sel.navDown;
      events[KeyEvent.DOM_VK_RETURN] = events[KeyEvent.DOM_VK_ENTER] =
        this._onEnter;
      events[KeyEvent.DOM_VK_ESCAPE] = this._onEscape;
      events[KeyEvent.DOM_VK_TAB] = this._onTab;

      return events;
    }

  , _onKeyDown: function ( event ) {
      // If there are no visible elements, don't perform selector navigation.
      // Just pass this up to the upstream onKeydown handler
      if ( !this.refs.sel ) { return this.props.onKeyDown( event ); }

      var handler = this.eventMap()[event.keyCode];

      if ( handler ) {
        handler( event );
      } else {
        return this.props.onKeyDown( event );
      }
      // Don't propagate the keystroke back to the DOM/browser
      event.preventDefault();
    }

  , componentWillReceiveProps: function ( nextProps ) {
      if ( nextProps.defaultValue !== this.props.defaultValue ) {
        let value = nextProps.defaultValue;
        this.setState({ entryValue : value
                    , visible    : this.getOptionsForValue(
                                    value, nextProps.options )
      });
      }
    }

  // Uncomment this if need be
  // , componentDidUpdate: function ( prevProps, prevState ) {
  //   }

  , _renderHiddenInput: function ( ) {
      if ( !this.props.name ) {
        return null;
      }

      return (
        <input
          type="hidden"
          name={ this.props.name }
          value={ this.state.selection }
        />
      );
    }

  , render: function ( ) {
      var inputClasses = {};
      inputClasses[this.props.customClasses.input] =
        !!this.props.customClasses.input;
      var inputClassList = classNames( inputClasses );

      var classes = { typeahead: true };
      classes[this.props.className] = !!this.props.className;
      var classList = classNames( classes );

      return (
        <div className={classList}>
          { this._renderHiddenInput() }
          <TWBS.Input
              ref          = "entry"
              type         = "text"
              placeholder  = { this.props.placeholder }
              className    = { inputClassList }
              value        = { this.state.entryValue }
              onKeyPress   = { this.props.onKeyPress }
              onChange     = { this._onTextEntryUpdated }
              onKeyDown    = { this._onKeyDown } />
          { this._renderIncrementalSearchResults() }
        </div>
      );
    }

  }
);

module.exports = FuzzyTypeAhead;
