// Subscriptions Debug Tab
// =============

"use strict";

var _     = require("lodash");
var React = require("react");
var TWBS  = require("react-bootstrap");

// Middleware
var SubscriptionsStore  = require("../../stores/SubscriptionsStore");

var Subscriptions = React.createClass({

    getInitialState: function() {
      return {
          // TODO: Make this work with the new subscriptions architecture
          subscriptions : SubscriptionsStore.getAllSubscriptions()
      };
    }

  , componentDidMount: function() {
      SubscriptionsStore.addChangeListener( this.handleMiddlewareChange );
    }

  , componentWillUnmount: function() {
      SubscriptionsStore.removeChangeListener( this.handleMiddlewareChange );
    }

  , handleMiddlewareChange: function( namespace ) {
      var newState = {};

      switch ( namespace ) {
        case "subscriptions":
          var availableServices = SubscriptionsStore.getAllSubscriptions();
          newState.services = availableServices;
          break;
      }

      this.setState( newState );
    }

  , createRow: function( namespace, index ) {
      return (
        <tr key={ index }>
          <td>{ namespace }</td>
          <td>{ this.state.subscriptions[ namespace ] }</td>
        </tr>
      );
    }

  , render: function() {
      var subscriptionsContent = null;

      if ( _.isEmpty( this.state.subscriptions ) ) {
        subscriptionsContent = <h3 className="text-center">No log content</h3>;
      } else {
        var subscriptionKeys = _.sortBy(
          _.keys( this.state.subscriptions ), function ( key ) {
            return this.state.subscriptions[ key ];
          }.bind(this)
        );

        subscriptionsContent = (
          <TWBS.Table responsive>
            <thead>
              <tr>
                <th>Namespace</th>
                <th>{"Number of subscribed components"}</th>
              </tr>
            </thead>
            <tbody>
              { subscriptionKeys.map( this.createRow ) }
            </tbody>
          </TWBS.Table>
        );
      }

      return (
        <div className="debug-content-flex-wrapper">

          <TWBS.Col xs={6} className="debug-column" >

            <h5 className="debug-heading">Active Subscriptions</h5>
            <div className="debug-column-content">
              { subscriptionsContent }
            </div>

          </TWBS.Col>

          <TWBS.Col xs={6} className="debug-column" >

            {/* TODO: Should something go here? */}

          </TWBS.Col>
        </div>
      );
    }

});

module.exports = Subscriptions;
