// Main App Wrapper
// ================
// Top level controller-view for FreeNAS webapp

"use strict";

import React from "react";

import { RouteHandler } from "react-router";

import routerShim from "../components/mixins/routerShim";

// WebApp Components
import BusyBox from "../components/BusyBox";
import NotificationBar from "../components/WebApp/NotificationBar";
import InformationBar from "../components/WebApp/InformationBar";
import PrimaryNavigation from "../components/PrimaryNavigation";
import DebugTools from "../components/DebugTools";


const FreeNASWebApp = React.createClass({

    mixins: [ routerShim ]

  , componentDidMount: function () {
      this.calculateDefaultRoute( "/", "dashboard", "is" );
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      this.calculateDefaultRoute( "/", "dashboard", "is" );
    }

  , render: function () {

      return (
        <div className="app-wrapper">
          {/* TODO: Add Modal mount div */}

          {/* Modal windows for busy spinner and/or FreeNAS login
                -- hidden normally except when invoked*/}
          <BusyBox />

          {/* Header containing system status and information */}
          <NotificationBar />

          <div className="app-content">
            {/* Primary navigation menu */}
            <PrimaryNavigation />

            {/* Primary view */}
            <RouteHandler />

            {/* User-customizable component showing system events */}
            <InformationBar />
          </div>

          <footer className="app-footer">
          </footer>

          <DebugTools />
        </div>
      );
    }

});

export default FreeNASWebApp;
