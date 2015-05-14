// Middleware Flux Store
// =====================
// Maintain consistent information about the general state of the middleware
// client, including which channels are connected, pending calls, and blocked operations.

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

var CHANGE_EVENT = "change";

var _subscribed = {};

// SCHEMA
// _subscribed = {
//     "foo.bar": {
//         MyReactComponent : 2
//       , SchmoopyPoo      : 1
//     }
//   , "doop.zoop": {
//         BusyBox : 1
//     }
// }

// <subscriptions>
//   <namespaces>
//     <component names> : <subscribed instances>


var SubscriptionsStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function () {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  // SUBSCRIPTIONS
  , getAllSubscriptions: function () {
      return _subscribed;
    }

  , getSubscriptionsByMask: function( mask ) {
      return _subscribed[ mask ];
    }

  , getNumberOfSubscriptionsForMask: function( mask ) {
      var numberSubscribed = 0;

      if ( _.isObject( _subscribed[ mask ] ) ) {
        _.forEach( _subscribed[ mask ], function( subscribedData ) {
          if ( typeof subscribedData === "number" ) {
            numberSubscribed += subscribedData;
          }
        });
        return numberSubscribed;
      } else {
        return 0;
      }
    }

});

SubscriptionsStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;
  var newSubscriptions = {};

  switch( action.type ) {

    // Subscriptions
    case ActionTypes.SUBSCRIBE_COMPONENT_TO_MASKS:
      newSubscriptions = _.cloneDeep( _subscribed );

      _.forEach( action.masks, function( mask ) {
        if ( _.isObject( newSubscriptions[ mask ] ) ) {
          if ( _.isNumber( newSubscriptions[ mask ][ action.componentID ] ) ) {
            newSubscriptions[ mask ][ action.componentID ]++;
          } else {
            newSubscriptions[ mask ][ action.componentID ] = 1;
          }
        } else {
          newSubscriptions[ mask ] = {};
          newSubscriptions[ mask ][ action.componentID ] = 1;
        }
      });

      _subscribed = newSubscriptions;

      SubscriptionsStore.emitChange();
      break;

    case ActionTypes.UNSUBSCRIBE_COMPONENT_FROM_MASKS:
      newSubscriptions = _.cloneDeep( _subscribed );

      _.forEach( action.masks, function( mask ) {
        if ( _.isObject( newSubscriptions[ mask ] ) ) {
          if ( newSubscriptions[ mask ][ action.componentID ] <= 1 ) {
            delete newSubscriptions[ mask ][ action.componentID ];
          } else {
            newSubscriptions[ mask ][ action.componentID ]--;
          }
        } else {
          console.warn( "Tried to unsubscribe from '" + mask + "', but Flux store shows no active subscriptions.");
        }

        if ( _.isEmpty( newSubscriptions[ mask ] ) ) {
          delete newSubscriptions[ mask ];
        }
      });

      _subscribed = newSubscriptions;

      SubscriptionsStore.emitChange();
      break;

    case ActionTypes.UNSUBSCRIBE_ALL:
      // TODO: Should this be the default?
      _subscribed = newSubscriptions;
      SubscriptionsStore.emitChange();
      break;

    default:
      // No action
  }
});

module.exports = SubscriptionsStore;
