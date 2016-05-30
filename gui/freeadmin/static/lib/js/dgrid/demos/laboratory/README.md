## Overview

The dgrid Laboratory is built using dgrid and provides a UI for defining and configuring your own dgrid.
The configuration will be rendered in a demo grid and if you click the "Code" button you can see source code for
creating the grid in your own application. While the Laboratory can be helpful in getting started creating and
configuring your own grid, you will definitely want to read dgrid's [documentation](../../doc) and
[tutorials](http://dgrid.io/#tutorials).

The documentation below gives some information on the overall architecture of the Laboratory and some more detailed
information on some of its more prominent modules.

#### Module hierarchy

* `Laboratory`
	* `ColumnEditor`
		* `ColumnGrid`
		* `ColumnConfigForm`
	* `FeatureEditor`
		* `FeatureGrid`
		* `ConfigForm` subclasses

## Widget communication

In addition to the typical parent-child widget communication, and occasional cross-widget communication,
the Laboratory listens at the top level (`Laboratory.js`) for data update events in order to keep the demo grid and
generated code updated in real time.

### Pub-sub topics

* **/configuration/changed**: Indicates that some data directly related to the display of the demo grid or
	generated code has changed
	* Publishers:
		* `ColumnGrid`: Published when the grid's store is modified
		* `FeatureEditor`: Published when the `FeatureGrid`'s store is modified
		* `ConfigForm`: Published when the form's `value` property changes
	* Subscribers:
		* `Laboratory`: Keeps the demo grid or generated code updated (depending on which is visible)

* **/column/changed**: Indicates that column configuration data has been updated in the UI
	* Publishers:
		* `ColumnConfigForm`: Published when the form's `value` property changes
	* Subscribers:
		* `ColumnGrid`: Keeps the store data constantly in sync with the UI form values

* **/store/columns/update**: Indicates that column configuration data has been updated in the store
	* Publishers:
		* `ColumnGrid`: Published when the grid's store is modified
	* Subscribers:
		* `configForms/Tree`: Updates the list of columns names so the user can select which one should render the
			tree expando

* **/feature/select**: Indicates that a feature (dgrid mixin) has been selected (or de-selected)
	* Publishers:
		* `FeatureGrid`: Published when the grid's editable fields change (`dgrid-datachange` event)
	* Subscribers:
		* `ColumnConfigForm`: Updates which column features are visible for configuration

* **/columnConfig/hidden**: Indicates changes to the hidden state of fields in the column configuration form.
	Passes an object hash whose keys correspond to the names of currently hidden fields.
	* Publishers:
		* `ColumnConfigForm`: Published in reaction to the `/feature/select` topic
	* Subscribers:
		* `ColumnGrid`: Updates column configurations to prune any properties which are no longer applicable

## Modules

### Laboratory

This is the top-level widget. It provides the full-page UI layout and manages child widgets. While the functionality of most components is encapsulated in child widgets, `Laboratory` directly manages some items itself:

* Tab navigation
* Updating the demo grid (`_showDemoGrid`) or generated code (`_generateCode`), depending on which is visible
	* Both the `_showDemoGrid` and `_generateCode` methods rely on the `_generateGridOptions` method to read the current
		configuration from the UI and calculate a dgrid options object to pass to the grid constructor function
* The "About" dialog

### ColumnEditor

This widget is initially visible when the page is loaded in the far left pane in the tab titled "Columns". It is a lightweight container for the `ColumnGrid` and `ColumnConfigForm` widgets.

#### API

* `get('columns')`: Returns an array of objects from the store that represent the user-defined columns; proxies to
	`ColumnGrid#get('columns')`
* `addColumn` and `removeColumn`: Provide the ability to add and remove user-defined columns; these methods proxy to
	the respective methods on `ColumnGrid`

### ColumnGrid

This widget is a little more than just a grid - it's a templated widget that contains a grid, but it also manages
the grid's store and the new column entry field in the UI (visible directly above the grid).

#### API

* `get('columns')`: Returns an array of objects from the store that represent the user-defined columns
* `addColumn(label)`: Adds a new column to the grid with the specified label, and auto-generates a field name based on
	that label
* `removeColumn(target)` (where `target` can be any value supported by dgrid's
	[`row` method](../../doc/components/core-components/List.md#method-summary)): Removes the associated column definition
	from the store (and grid)

### ColumnConfigForm

This widget provides the UI for editing user-defined columns. Some sections are hidden or visible depending on
which mixins are enabled (e.g. `Editor`, `ColumnHider`, etc.). It extends `dijit/form/_FormMixin` for basic
form management and the `get/set('value')` methods. As a result, when the widget's `value` is set,
any values in the object provided that do not map directly to fields in the form are discarded.

In order to correctly update items in the store, whenever the `value` is set, the `id` property (which is
not represented by any of the form fields) is persisted by the custom setter method. The custom getter method restores
the `id` property to the object returned by `ColumnConfigForm#get('value')`.

### FeatureEditor

This widget encapsulates the functionality in the "Grid Features" and "Column Features" tabs. It extends
`dijit/layout/StackContainer` and contains one `FeatureGrid` and multiple widgets that extend `configForms/ConfigForm`.
The config form widgets are defined by two components:

1. An item in the array defined in the `data/features` module
2. (Optional) If the feature has configurable properties, the UI to edit them should be provided in a module that
extends `configForms/ConfigForm`. The module ID of the config form module should be indicated via the item's
`configModule` property in the `data/features` module.

#### API

* `getModuleConfig(moduleId)`: Returns an object representing the configured options for the specified dgrid module ID
* `isSelected(moduleId)`: Returns a boolean value indicating if the specified dgrid mixin module ID is selected
* `filter(query)`: Filters the `FeatureGrid` by the specified query
* `get('expandoColumn')`: If the `dgrid/Tree` mixin has been enabled, this method returns the name of the column that has been configured to render the tree expando icon
* `set('featureType', featureType)` (where `featureType` is `'grid'` or `'column'`): Filters the `FeatureGrid` by the
	specified type; proxies to `FeatureGrid#set('featureType')`. The same grid is displayed in both the "Grid Features"
	and "Column Features" tabs using this method to filter which rows are displayed.

### FeatureGrid

Like the `ColumnGrid` widget, this is a templated widget that encapsulates not only the grid but also its store.
Logic is also included to prevent incompatible configurations (e.g. `OnDemandGrid` with `dgrid/extensions/Pagination`).

#### API

* `set('featureType', featureType)` (where `featureType` is `'grid'` or `'column'`): Filters the grid by the specified
	type
* `set('gridModule', gridModule)` (where `gridModule` is `'Grid'` or `'OnDemandGrid'`): sets the base grid module of the
	user-defined grid and prevents incompatible combinations

### ConfigForm

This module should not be instantiated directly. It provides the basic functionality for
grid feature configuration forms (e.g. `Selection`, `Tree`, etc.).

* Renders a "Done" button to return to dismiss the form and return to the grid
* Extends `dijit/form/_FormMixin` with custom accessor/mutator methods
	* `set('value', value)`: Unspecified properties will be set to their default value
	* `get('value')`: Properties whose values match the default value will be omitted

Each subclassing module should provide an object on the `defaultsObject` property that defines default values for
configuration properties. This can typically be achieved by providing the dgrid module's prototype, since these modules
define their configurable properties and their default values. The default values are used both to initially populate
the form and to filter values - if the user has not changed the value from the default, it will be omitted from the
generated code.  `defaultsObject` is never modified.

Each subclass should also specify `moduleName` and `documentationUrl` properties to be displayed in the
config form's UI.

All currently-implemented subclasses of `ConfigForm` are located under `widgets/configForms`.
