// Subscriptions Debug Tab
// =============

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

var componentLongName = "Debug Tools - Subscriptions Tab";

// Disclosure Triangles
import DiscTri from "../common/DiscTri";

// Middleware
import SubscriptionsStore from "../../stores/SubscriptionsStore";
import MiddlewareClient from "../../middleware/MiddlewareClient";


var Subscriptions = React.createClass({

    getInitialState: function () {
      return {
          subscriptions : SubscriptionsStore.getAllSubscriptions()
        , subsMasks     : ""
      };
    }

  , componentDidMount: function () {
      SubscriptionsStore.addChangeListener( this.handleMiddlewareChange );
    }

  , componentWillUnmount: function () {
      SubscriptionsStore.removeChangeListener( this.handleMiddlewareChange );
    }

  , handleMiddlewareChange: function () {
      this.setState({
          subscriptions : SubscriptionsStore.getAllSubscriptions()
      });
    }

  , handleMaskInputChange: function( event ) {
      this.setState({
          subsMasks : event.target.value
      });
    }

  , handleSubsSubmit: function () {
      MiddlewareClient.subscribe( this.state.subsMasks.replace(/\s/g,"").split(","), componentLongName);
    }

  , createList: function( item, index ) {
      return (
        <li key={ index }>{ item }</li>
      );
    }

  , createRow: function( namespace, index ) {
      var listItems = [];
      _.forEach( this.state.subscriptions[ namespace ], function ( value, key ) {
        listItems.push(String(key).concat(" : ", value));
      });
      return (
        <tr key={ index }>
          <td>{ namespace }</td>
          <td>{ _.sum(this.state.subscriptions[ namespace ]) }</td>
          <td>
            <DiscTri key={ index } defaultExpanded={false}>
              <ul>{ listItems.map( this.createList ) }</ul>
            </DiscTri>
          </td>
        </tr>
      );
    }

  , render: function () {
      var subscriptionsContent = null;
      var removeALL = MiddlewareClient.unsubscribeALL;

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
                <th>{"Total Number of subscribed components"}</th>
                <th>{"Individual ComponentID counts"}</th>
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

            <h5 className="debug-heading">Add Subsriptions</h5>
            <TWBS.Row>
              <TWBS.Col xs={5}>
                <TWBS.Input type        = "textarea"
                            style       = {{ resize: "vertical", height: "34px" }}
                            placeholder = "Subscription Mask(s)"
                            onChange    = { this.handleMaskInputChange }
                            value       = { this.state.subsMasks } />
              </TWBS.Col>
            </TWBS.Row>
            <TWBS.Row>
              <TWBS.Col xs={2}>
                <TWBS.Button bsStyle = "primary"
                             onClick = { this.handleSubsSubmit }
                             block>
                  {"Submit"}
                </TWBS.Button>
              </TWBS.Col>
            </TWBS.Row>

            <h5 className="debug-heading">Remove Subscriptions</h5>
              <div className="debug-column-content">
                <TWBS.Button block bsStyle = "danger"
                             onClick = { removeALL }>
                  {"Remove All Subscriptions"}
                </TWBS.Button>
              </div>

          </TWBS.Col>
        </div>
      );
    }

});

module.exports = Subscriptions;
