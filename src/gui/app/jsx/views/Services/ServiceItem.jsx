// Service Item Template
// =====================

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import routerShim from "../../components/mixins/routerShim";
import clientStatus from "../../components/mixins/clientStatus";

import viewerUtil from "../../components/Viewer/viewerUtil";

import ServicesMiddleware from "../../middleware/ServicesMiddleware";
import ServicesStore from "../../stores/ServicesStore";

import ToggleSwitch from "../../components/common/ToggleSwitch";

const ServiceView = React.createClass({

  propTypes: {
    item: React.PropTypes.object.isRequired
  }

  , getInitialState: function () {
      return { serviceState: ( this.props.item.state === "running"
                                                      ? true
                                                      : false ) };
    }

  , configureService: function ( action, command ) {

    switch ( action ) {
      // Start stop
      case 1:
        ServicesMiddleware.configureService( this.props.item.name
                                           , { enable: command } );
      break;

      // Start stop once
      case 2:
        ServicesMiddleware.updateService( this.props.item.name
                                           , command );
      break;



      ServicesMiddleware.updateService( serviceName, action );
    }
  }

  , render: function () {

    var pid = null;

    if ( this.props.item["pid"]
         && typeof this.props.item["pid"]
         === "number" ) {
      pid = <h4 className="text-muted">
              { viewerUtil.writeString( "PID: " + this.props.item["pid"]
                                        , "\u200B" ) }
            </h4>;
    }

    return (
      <div className="viewer-item-info">
        <TWBS.Grid fluid>

        {/* General information */}
        <TWBS.Row>
          <TWBS.Col xs={3}
                    className="text-center">
            <viewerUtil.ItemIcon primaryString  = { this.props.item["name"] }
                                 fallbackString = { this.props.item["name"] } />
          </TWBS.Col>
          <TWBS.Col xs={9}>
            <h3>{ this.props.item["name"] }</h3>
            <h4 className="text-muted">
              { viewerUtil.writeString( this.props.item["state"], "\u200B" ) }
            </h4>

            { pid }

            <hr />
            <TWBS.ButtonToolbar>
              <TWBS.SplitButton title   = { "Enable" }
                                bsStyle = { "success" }
                                key     = { "1" }
                                onClick = { this.configureService.bind( null, 1
                                            , true ) } >
                <TWBS.MenuItem eventKey="1"
                               onClick = { this.configureService
                                           .bind( null, 2, "start" ) }>
                  { "Enable once" }
                </TWBS.MenuItem>
                <TWBS.MenuItem eventKey="2">
                  { "Enable after reboot" }
                </TWBS.MenuItem>
              </TWBS.SplitButton>
              <TWBS.SplitButton title   = { "Disable" }
                                bsStyle = { "danger" }
                                key     = { "2" }
                                onClick = { this.configureService
                                            .bind( null, 1, false ) } >
                <TWBS.MenuItem eventKey="1"
                               onClick = { this.configureService
                                           .bind( null, 2, "stop" ) }>
                  { "Disable once" }
                </TWBS.MenuItem>
                <TWBS.MenuItem eventKey="2">
                  { "Disable after reboot" }
                </TWBS.MenuItem>
                <TWBS.MenuItem eventKey="3">
                  { "Disconnect current users" }
                </TWBS.MenuItem>
                </TWBS.SplitButton>
            </TWBS.ButtonToolbar>

          </TWBS.Col>
        </TWBS.Row>

        </TWBS.Grid>
      </div>
    );
  }

});

const ServiceItem = React.createClass({

  propTypes: {
    viewData : React.PropTypes.object.isRequired
  }

  , mixins: [ routerShim, clientStatus ]

  , getInitialState: function () {
      return {
        targetService : this.getServiceFromStore()
        , currentMode   : "view"
        , activeRoute   : this.getDynamicRoute()
      };
    }

  , componentDidUpdate: function ( prevProps, prevState ) {
      var activeRoute = this.getDynamicRoute();

      if ( activeRoute !== prevState.activeRoute ) {
        this.setState({
          targetService : this.getServiceFromStore()
          , currentMode   : "view"
          , activeRoute   : activeRoute
        });
      }
    }

  , componentDidMount: function () {
      ServicesStore.addChangeListener( this.updateServiceTarget );
    }

  , componentWillUnmount: function () {
      ServicesStore.removeChangeListener( this.updateServiceTarget );
    }

  , getServiceFromStore: function () {
      return ServicesStore
             .findServiceByKeyValue( this.props.viewData.format["selectionKey"]
                                     , this.getDynamicRoute() );
    }

  , updateServiceTarget: function () {
      this.setState({ targetService: this.getServiceFromStore() });
    }

  , render: function () {
      var DisplayComponent = null;

      if ( this.state.SESSION_AUTHENTICATED && this.state.targetService ) {

        // DISPLAY COMPONENT
        var childProps = {
          handleViewChange : this.handleViewChange
          , item             : this.state.targetService
          , viewData         : this.props.viewData
        };

        switch ( this.state.currentMode ) {
          default:
          case "view":
            DisplayComponent = <ServiceView { ...childProps } />;
          break;

          case "edit":
            // TODO
          break;
        }

      }

      return (
        <div className="viewer-item-info">

          { DisplayComponent }

        </div>
      );
    }

});

export default ServiceItem;
