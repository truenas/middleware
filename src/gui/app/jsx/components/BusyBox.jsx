// Busy Box
// =========
// Just a Busy Spinner for Restarts and Shutdowns

"use strict";

var componentLongName = "BusyBox";

import React from "react";

// Middleware
import MiddlewareClient from "../middleware/MiddlewareClient";

// Middleware Store (this is needed for reconnection interval)
import MiddlewareStore from "../stores/MiddlewareStore"

// SessionStore stores the logged in user and the fact that login happened.
import SessionStore from "../stores/SessionStore";

// PowerStore
import PowerStore from "../stores/PowerStore";

// Power Middleware
import PowerMiddleware from "../middleware/PowerMiddleware";

// Throbber
import Throbber from "./common/Throbber";

// Twitter Bootstrap React components
import TWBS from "react-bootstrap";

var BusyBox = React.createClass(

  { propTypes: { animDuration : React.PropTypes.number
               , animDelay    : React.PropTypes.number
    }

  , getDefaultProps: function () {
      return { animDuration : 500
             , animDelay    : 0
      };
    }

  , getInitialState: function () {
      return { boxIsVisible  : false
             , userText      : ""
             , passText      : ""
             , busyText      : "Busy"
             , kickin        : false
             , loggedIn      : SessionStore.getLoginStatus()
             , operation     : "Connect you to FreeNAS"
             , reconnetTime  : 0
             , sockState     : false
      };
    }

  , componentDidMount: function () {
      SessionStore.addChangeListener( this.handleSessionChange );
      PowerStore.addChangeListener( this.handlePowerChange );
      MiddlewareStore.addChangeListener( this.handleMiddlewareChange );
      PowerMiddleware.subscribe( componentLongName );
      // this.updateBoxVisibility();
      // TODO: do we need the above?
    }

  , componentWillUnmount: function () {
      PowerStore.removeChangeListener( this.handlePowerChange );
      SessionStore.removeChangeListener( this.handleSessionChange );
      MiddlewareStore.removeChangeListener( this.handleMiddlewareChange );
      PowerMiddleware.unsubscribe( componentLongName );
    }

  , componentDidUpdate: function ( prevProps, prevState ) {
      if ( prevState.kickin !== this.state.kickin ||
           prevState.loggedIn !== this.state.loggedIn ||
           prevState.sockState !== this.state.sockState ) {
        this.updateBoxVisibility();
      }
    }

  , updateBoxVisibility: function () {
      if ( this.state.kickin ||
           !this.state.loggedIn ||
           !this.state.sockState ) {
        if ( !this.state.boxIsVisible ) { this.showBusyBox(); };
      } else {
        if ( this.state.boxIsVisible ) { this.showBusyBox(); };
      }
    }

  , showBusyBox: function () {
      this.setState({ boxIsVisible: true });
      // clear the cached password!
      this.setState({ passText: "" });
      Velocity( React.findDOMNode( this.refs.Busy )
             , "fadeIn"
             , { duration: this.props.animDuration } );
    }

  , hideBusyBox: function () {
      this.setState({ boxIsVisible: false });
      Velocity( React.findDOMNode( this.refs.Busy )
             , "fadeOut"
             , { duration : this.props.animDuration
               , delay    : this.props.animDelay }
             );

      this.animTimeout = setTimeout( function ( ) {
         this.setState({ boxIsVisible: false });
       }.bind( this )
       , this.props.animDuration + this.props.animDelay + 250
      );
    }

  , handleSessionChange: function () {
      this.setState({ loggedIn: SessionStore.getLoginStatus() });
    }

  , handlePowerChange: function () {
      let retcode = PowerStore.isEventPending();
      this.setState({ kickin    : retcode[0]
                    , operation : retcode[1]
      });
    }

  , handleMiddlewareChange: function () {
      let retcode = MiddlewareStore.getSockState();
      this.setState({ sockState     : retcode[0]
                    , reconnetTime  : Math.round( retcode[1] / 1000 )
      })
    }

  , handleUserChange: function ( event ) {
      this.setState({ userText: event.target.value });
    }

  , handlePassChange: function ( event ) {
      this.setState({ passText: event.target.value });
    }

  , handleKeydown: function ( event ) {
      if ( event.which === 13 && this.state.userText.length ) {
        this.handleLoginClick();
      }
    }

  , handleLoginClick: function ( event ) {
      // TODO: Input validation for user/pass. What are the rules?
      MiddlewareClient.login( "userpass"
                            , [ this.state.userText
                              , this.state.passText ] );
    }

  , render: function () {
      var busyBody = ( <div ref="Busy"  style={{ opacity: 0 }}/> );

      if ( this.state.boxIsVisible ) {
        if ( !this.state.sockState || this.state.kickin ) {
          let throbberprops     = {};
          throbberprops.bsStyle = "primary";
          throbberprops.size    = 60;
          let dispMsg           = (
            <h2>{ "Please wait while I " + this.state.operation }</h2>
          );
          if ( !this.state.sockState ) {
            dispMsg = (
              <span>
                <h2>{ "Reconnection you to FreeNAS in "
                      + this.state.reconnetTime
                      + " seconds" }
                </h2>
                <TWBS.Button block bsStyle="info"
                             onClick = {
                               MiddlewareClient.reconnectHandle.reconnectNow.bind( MiddlewareClient.reconnectHandle ) }>
                  {"Reconnect Now"}
                </TWBS.Button>
                <br />
              </span>
            );

          }

          busyBody = (
            <div className="overlay-dark" ref="Busy" style={{ opacity: 0 }}>
              <div className="overlay-window">
                <div>
                  { dispMsg }
                  <Throbber {...throbberprops} />
                </div>
              </div>
            </div>
          );
        } else if ( !this.state.loggedIn ) {
          busyBody = (
            <div className="overlay-dark" ref="Busy" style={{ opacity: 0 }}>
              <div className="overlay-window">

                <h3>{"Welcome to FreeNAS 10"}</h3>
                <hr />

                <div className="form-group">
                  <input className   = "form-control"
                         type        = "text"
                         value       = { this.state.userText }
                         onChange    = { this.handleUserChange }
                         onKeyDown   = { this.handleKeydown }
                         placeholder = "Username" />
                </div>
                <div className="form-group">
                  <input className   = "form-control"
                         type        = "password"
                         value       = { this.state.passText }
                         onChange    = { this.handlePassChange }
                         onKeyDown   = { this.handleKeydown }
                         placeholder = "Password" />
                </div>

                <TWBS.Button block bsStyle="info"
                             disabled = { this.state.userText.length ?
                                            false : true }
                             onClick  = { this.handleLoginClick }>{"Sign In"}
                </TWBS.Button>
              </div>
            </div>
          );
        }
      }

      return busyBody;
    }

  }
);

module.exports = BusyBox;
