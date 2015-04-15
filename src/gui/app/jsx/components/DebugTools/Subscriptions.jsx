// Subscriptions Debug Tab
// =============

"use strict";

var _     = require("lodash");
var React = require("react");
var TWBS  = require("react-bootstrap");

var componentLongName = "Debug Tools - Subscriptions Tab";

// Middleware
var SubscriptionsStore  = require("../../stores/SubscriptionsStore");
var MiddlewareClient    = require("../../middleware/MiddlewareClient");

var Icon                = require("../Icon");

var Subscriptions = React.createClass({

    getInitialState: function() {
      var subs = SubscriptionsStore.getAllSubscriptions();
      var listClass = {};
      _.forEach(subs,  function (value, key) {
         listClass[key] = false;
      });
      return {
          subscriptions : subs
        , listClass     : listClass
        , subsMasks     : ""
      };
    }

  , componentDidMount: function() {
      SubscriptionsStore.addChangeListener( this.handleMiddlewareChange );
    }

  , componentWillUnmount: function() {
      SubscriptionsStore.removeChangeListener( this.handleMiddlewareChange );
    }

  , handleMiddlewareChange: function() {
      var subs = SubscriptionsStore.getAllSubscriptions();
      var listClass = this.state.listClass;
      _.forEach(subs,  function (value, key) {
         if ( !_.has(listClass, key) ) {
           listClass[key] = false;
         }
      });
      this.setState({
          subscriptions : subs
        , listClass     : listClass
      });
    }

  , handleMaskInputChange: function( event ) {
      this.setState({
          subsMasks : event.target.value
      });
    }

  , handleSubsSubmit: function() {
      MiddlewareClient.subscribe( this.state.subsMasks.replace(/\s/g,"").split(","), componentLongName);
    }

  , discloseToggle: function( namespace ) {
      var listClass = this.state.listClass;
      listClass[namespace] = !listClass[namespace];
      this.setState({
        listClass : listClass
      });
  }

  , createList: function( item, index ) {
      return (
        <li key={ index }>{ item }</li>
      );
    }

  , createRow: function( namespace, index ) {
      var listItems = [];
      var glyphClass = "toggle-right";
      var tbClass    = "debug-disclosure-hide";
      var listHead   = "show";
      _.forEach( this.state.subscriptions[ namespace ], function ( value, key ) {
            listItems.push(String(key).concat(" : ", value));
          });

      if ( this.state.listClass[namespace] ) {
        glyphClass = "toggle-down";
        tbClass    = "debug-disclosure-show";
        listHead   = "hide";
      }

      return (
        <tr key={ index }>
          <td>{ namespace }</td>
          <td>{ _.sum(this.state.subscriptions[ namespace ]) }</td>
          <td>
            <span className={ tbClass }>
              <h6>
                <Icon glyph = { glyphClass }
                      icoSize = "1em"
                      onClick = { this.discloseToggle.bind(this, namespace) } />
                { listHead }
              </h6>
              <ul>{ listItems.map( this.createList ) }</ul>
            </span>
          </td>
        </tr>
      );
    }

  , render: function() {
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
