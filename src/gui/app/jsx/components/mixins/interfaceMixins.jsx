// Interface Editing Mixins
// ========================
// Various things that are needed for just about any view that will be editing interfaces.

'use strict';

import _ from 'lodash';

import IS from '../../stores/InterfacesStore';
import IM from '../../middleware/InterfacesMiddleware';

module.exports = {
  componentDidMount: function () {
      IS.addChangeListener( this.updateInterfacesInState );
    }
  , componentWillUnmount: function () {
      IS.removeChangeListener( this.updateInterfacesInState );
    }
  , updateInterfacesInState: function () {
      this.setState( { interfacesList: IS.getAllInterfaces() } );
    }
};
