// Notification Bar
// ================
// Part of the main webapp's window chrome. Positioned at the top of the page,
// this bar details the alerts, events, and tasks that represent the current
// state of the system

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import MiddlewareClient from "../../middleware/MiddlewareClient";
import SS from "../../stores/SessionStore";

import LogQueue from "./NotificationBar/LogQueue";


var NotificationBar = React.createClass(
  { getInitialState: function () {
    return (
      { visibleLog: ""

      , currentUser: SS.getCurrentUser()

      // TODO: Replace dummy data with Middleware data in a Flux store
      , active:
        { alerts:
          [ { description : <span>Reading Error at position 456 in pool <strong>HONK1</strong></span>
            , status      : "warning"
            , details     : "Error code #1234 Details about this error"
            }
          , { description : <span>Reading Error at position 123 in pool <strong>HONK1</strong></span>
            , status      : "warning"
            , details     : "Error code #1234 Details about this error"
            }
          , { description : <span>Reading Error at position 123 in pool <strong>HONK1</strong></span>
            , status      : "warning"
            , details     : "Error code #1234 Details about this error"
            }
          , { description : <span>Reading Error at position 123 in pool <strong>HONK1</strong></span>
            , status      : "warning"
            , details     : "Error code #1234 Details about this error"
            }
          ]
        , events:
          [ { description : <span>User <strong>Jakub Klama</strong> logged in as <strong>administrator</strong></span>
            , status      : "info"
            , details     : "Nov 14 11:20am"
            }
          ]
        , actions:
          [ { description : <span>Running <strong>SCRUB</strong> on pool <strong>HONK1</strong></span>
            , status      : "in-progress"
            , progress    : 60
            , details     : "Run by Jakub Klama 11 minutes ago"
            }
          , { description : <span>Waiting to run <strong>SCRUB</strong> on pool <strong>KEVIN</strong></span>
            , status      : "pending"
            , progress    : 0
            , details     : "Run by Jakub Klama 3 minutes ago"
            , info        : "Waiting for previous task (Scrub on pool HONK1)"
            }
          ]
        }

      // TODO: Replace dummy data with Middleware data in a Flux store
      , log:
        { alerts : []
        , events :
          [ { description : <span>User <strong>Kevin Bacon</strong> created dataset <strong>KEVIN</strong></span>
            , status      : "info"
            , details     : "Nov 14 11:10am"
            }
          ]
        , actions : []
        }
      }
    );
  }

  // TODO: These should use EventBus
  , componentDidMount: function () {
    SS.addChangeListener( this.updateCurrentUser );
    window.addEventListener( "click", this.makeAllInvisible );
  }

  , componentWillUnmount: function () {
    SS.addChangeListener( this.updateCurrentUser );
    window.removeEventListener( "click", this.makeAllInvisible );
  }

  , updateCurrentUser: function ( event ) {
    this.setState({ currentUser: SS.getCurrentUser() });
  }

  , makeAllInvisible: function ( event ) {
    this.setState({ visibleLog: "" });
  }

  , makeEventsVisible: function ( event ) {
    this.setState({ visibleLog: "events" });
  }

  , makeAlertsVisible: function ( event ) {
    this.setState({ visibleLog: "alerts" });
  }

  , makeActionsVisible: function ( event ) {
    this.setState({ visibleLog: "actions" });
  }


  , render: function () {
    return (
      <header className = "app-header notification-bar" >
        <img
          style = {{ margin: "7px 0 0 15px", height: "32px" }}
          src   = "/img/freenas-icon.png"
        />
        <img
          style = {{ margin: "8px 0 0 10px", height: "20px" }}
          src   = "/img/freenas-logotype.png"
        />

        <div className="user-info">

          {/* System Events */}
          <LogQueue glyph             = "flag"
                    className         = "notification-info"
                    requestVisibility = { this.makeEventsVisible }
                    visible           = { this.state.visibleLog === "events" }
                    active            = { this.state.active.events }
                    log               = { this.state.log.events } />

          {/* Alert Messages */}
          <LogQueue glyph             = "warning"
                    className         = "notification-warning"
                    requestVisibility = { this.makeAlertsVisible }
                    visible           = { this.state.visibleLog === "alerts" }
                    active            = { this.state.active.alerts }
                    log               = { this.state.log.alerts } />

          {/* System Tasks/Actions */}
          <LogQueue glyph             = "list-alt"
                    className         = "notification-default"
                    requestVisibility = { this.makeActionsVisible }
                    visible           = { this.state.visibleLog === "actions" }
                    active            = { this.state.active.actions }
                    log               = { this.state.log.actions } />

          <TWBS.DropdownButton
            pullRight
            title     = { this.state.currentUser }
            bsStyle   = "link"
            className = "user online"
          >
            <TWBS.MenuItem
              key     = { 0 }
              onClick = { MiddlewareClient.logout.bind( MiddlewareClient ) }
            >
              {"Logout"}
            </TWBS.MenuItem>
          </TWBS.DropdownButton>

        </div>
      </header>
    );
  }
});

export default NotificationBar;
