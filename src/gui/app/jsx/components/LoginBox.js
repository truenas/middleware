/** @jsx React.DOM */

// Login Box
// =========
// Authentication window for FreeNAS. Displayed whenever the middleware is in a logged out state.

"use strict";

var _     = require("lodash");
var React = require("react");

// Middleware
var MiddlewareClient = require("../middleware/MiddlewareClient");
var MiddlewareStore  = require("../stores/MiddlewareStore");

// Twitter Bootstrap React components
var TWBS = require("react-bootstrap");


var LoginBox = React.createClass({

    getInitialState: function() {
      return {
          userText      : ""
        , passText      : ""
        , authenticated : MiddlewareStore.getAuthStatus()
      };
    }

  , componentDidMount: function() {
      MiddlewareStore.addChangeListener( this.handleMiddlewareChange );
      this.updateBoxVisibility();
    }

  , componentWillUnmount: function () {
      MiddlewareStore.removeChangeListener( this.handleMiddlewareChange );
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      if ( prevState.authenticated !== this.state.authenticated ) {
        this.updateBoxVisibility();
      }
    }

  , updateBoxVisibility: function () {
      if ( this.state.authenticated ) {
        this.hideLoginBox();
      } else {
        this.showLoginBox();
      }
    }

  , showLoginBox: function () {
      Velocity( this.refs.login.getDOMNode()
                , "fadeIn"
                , { duration: "500" } );
    }

  , hideLoginBox: function () {
      Velocity( this.refs.login.getDOMNode()
                , "fadeOut"
                , { duration: "500" } );
    }

  , handleUserChange: function( event ) {
      this.setState({ userText: event.target.value });
    }

  , handlePassChange: function( event ) {
      this.setState({ passText: event.target.value });
    }

  , handleMiddlewareChange: function() {
      this.setState({ authenticated: MiddlewareStore.getAuthStatus() });
    }

  , handleKeydown: function( event ) {
      if ( event.which === 13 && this.state.userText.length ) {
        this.handleLoginClick();
      }
    }

  , handleLoginClick: function( event ) {

      // TODO: Input validation for user/pass. What are the rules?

      MiddlewareClient.login( this.state.userText, this.state.passText );
    }

  , render: function () {
      return (
        <div className="overlay-dark" ref="login">
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
                         disabled = { this.state.userText.length ? false : true }
                         onClick  = { this.handleLoginClick }>{"Sign In"}</TWBS.Button>
          </div>
        </div>
      );
    }

});

module.exports = LoginBox;
