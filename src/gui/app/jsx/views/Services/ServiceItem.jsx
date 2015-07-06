// Service Item Template
// =====================

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";
import Icon from "../../components/Icon";

import routerShim from "../../components/mixins/routerShim";
import clientStatus from "../../components/mixins/clientStatus";

import viewerUtil from "../../components/Viewer/viewerUtil";

import SM from "../../middleware/ServicesMiddleware";
import SS from "../../stores/ServicesStore";

import ToggleSwitch from "../../components/common/ToggleSwitch";

const ServiceView = React.createClass({

  propTypes: {
    item: React.PropTypes.object.isRequired
  }

  , configureService: function ( action, command ) {

    switch ( action ) {
      // Start stop
      case 1:
        SM.configureService( this.props.item["name"]
                                           , { enable: command } );
        break;

        // Start stop once
      case 2:
        SM.updateService( this.props.item["name"]
                                           , command );
        break;
    }
  }

  , render: function () {

    var pid = null;

    if ( this.props.item["pid"]
         && typeof this.props.item["pid"]
         === "number" ) {
      pid = <h4 className="text-muted">
              { "PID: " + this.props.item["pid"] }
            </h4>;
    }

    let startStopButton;

    switch ( this.props.item["state"].toLowerCase() ) {
      case "running":
        startStopButton = (
          <a onClick={ SM.updateService.bind( null
                                            , this.props.item["name"]
                                            , "STOP" ) }>
          <Icon glyph = "stop" icoSize = "3em" /></a> );
        break;
      case "unknown":
      case "stopped":
        startStopButton = (
          <a onClick={ SM.updateService.bind( null
                                            , this.props.item["name"]
                                            , "START" ) }>
          <Icon glyph = "play" icoSize = "3em" /></a> );
        break;
    }

    return (
      <div className="viewer-item-info">
        <TWBS.Grid fluid>

        {/* General information */}
        <TWBS.Row>
          <TWBS.Col xs={3}
                    className="text-center">
            <viewerUtil.ItemIcon primaryString  = { this.props.item["name"] }
                                 fallbackString = { this.props.item["name"] }
                                 seedNumber = { this.props.item["name"].length }
                                 />
          </TWBS.Col>
          <TWBS.Col xs={6}>
            <h3>{ this.props.item["name"] }</h3>
            <h4 className="text-muted">
              { this.props.item["state"] }
            </h4>

            { pid }

            <hr />
          </TWBS.Col>
          <TWBS.Col xs={3}>
            { startStopButton }
          </TWBS.Col>
        </TWBS.Row>
        <TWBS.Row>
          <TWBS.Col xs={12}>
            <TWBS.ButtonToolbar>
              <TWBS.SplitButton title   = { "Enable" }
                                bsStyle = { "success" }
                                key     = { "1" }
                                onClick = { this.configureService.bind( null, 1
                                            , true ) } >
                <TWBS.MenuItem eventKey="1"
                               onClick = { this.configureService
                                           .bind( null, 2, "START" ) }>
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
                                           .bind( null, 2, "STOP" ) }>
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

  mixins: [ routerShim, clientStatus ]

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
      SS.addChangeListener( this.updateServiceTarget );
    }

  , componentWillUnmount: function () {
      SS.removeChangeListener( this.updateServiceTarget );
    }

  , getServiceFromStore: function () {
      return SS
             .findServiceByKeyValue( this.props.keyUnique
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
