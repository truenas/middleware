// SHELL
// =====
// Common-use React component wrapping the various different shells that FreeNAS
// supports. Handles its own lifecycle and does not rely on a Flux store. Since
// it relies on single-use authentication tokens and has no persistent data,
// there is no need for the standard data flow model.

"use strict";

import React from "react";
import Terminal from "term.js";

import ShellMiddleware from "../../middleware/ShellMiddleware";

var Shell = React.createClass(
  {  ws             : null
  , term            : null
  , isAuthenticated : false

  , propTypes: {
      shellType: React.PropTypes.string
    }

  , getDefaultProps: function () {
      return {
        shellType: "/bin/sh"
      };
    }

  , componentDidMount: function () {
      ShellMiddleware.spawnShell( this.props.shellType, this.createNewShell );
    }

  , componentDidUpdate: function ( prevProps, prevState ) {
      if ( this.props.shellType !== prevProps.shellType ) {
        this.ws.close();
        this.term.destroy();
        this.isAuthenticated = false;
        ShellMiddleware.spawnShell( this.props.shellType, this.createNewShell );
      }
      if ( this.refs.termTarget.getDOMNode().clientHeight !== 0 ) {
        this.term.resize( 80
                        , this.refs.termTarget.getDOMNode().clientHeight * 0.05 );
      }
    }

  , createNewShell: function ( token ) {
      var url = window.location.protocol === "https:" ? "wss://" : "ws://"
              + document.domain + ":5000/shell";

      this.ws   = new WebSocket( url );
      this.term = new Terminal({ cols       : 80
                               , rows       : 14
                               , screenKeys : true
      });

      this.ws.onopen = function ( event ) {
        this.ws.send( JSON.stringify({ token: token }) );
      }.bind( this );

      this.ws.onmessage = function ( event ) {
        if ( !this.isAuthenticated ) {
          if ( JSON.parse( event.data )["status"] === "ok" ) {
            this.isAuthenticated = true;
          }

          return;
        }

        this.term.write( event.data );
      }.bind( this );

      this.term.on( "data", function ( data ) {
        this.ws.send( data );
      }.bind( this ) );

      this.term.open( this.refs.termTarget.getDOMNode() );
    }

  , render: function () {
      return (
        <div className="termFlex" ref="termTarget" />
      );
    }

  }
);

module.exports = Shell;
