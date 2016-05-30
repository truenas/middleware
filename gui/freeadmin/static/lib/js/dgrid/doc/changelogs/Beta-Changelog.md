This document explains significant changes to dgrid between the alpha (0.2.0)
and initial beta (0.3.0) release.

## General

### column plugin names are now lowercase

Formerly, column plugins and the named arguments storing their module return values
had their first letter capitalized.  However, given that these plugins are in
fact simply functions which modify (and return) their first passed argument,
and are not in fact constructors, their nomenclature has been amended to
all-lowercase to avoid confusion, and to further convey that they are intended
to be run without the `new` keyword.

When running on a case-insensitive filesystem (e.g. Windows, or Mac OS X by
default), this change likely won't have any immediate visible effect on
existing code which requests the module with an initial capital letter.
However, revising code to reference the all-lowercase module ID is encouraged.

### new TouchScroll implementation

The TouchScroll module provides touch-event-based scrolling for dgrid
components on touch devices.  Originally this module was borrowed from a
snapshot of a dojox/mobile module, but this implementation blocked several
dgrid features from working correctly on touch devices.

That module has been replaced by a new barebones implementation written from the
ground up.  Further development on this module is likely to occur.

### additional extensions

The following extensions have been added since v0.2:

* [ColumnReorder](../components/extensions/ColumnReorder.md): allows reordering columns in simple grids via DnD
* [ColumnHider](../components/extensions/ColumnHider.md): allows dynamically hiding/showing grid columns from a simple menu
* [Pagination](../components/extensions/Pagination.md): adds controls for discrete pagination

## CSS

### column-<id> and columnset-* classes now prefixed with dgrid-

The `column-<id>` classes added by the Grid module, and the `columnset-*`
classes added by the ColumnSet mixin, have been renamed to include the `dgrid-`
prefix like most other classes automatically added by dgrid components.

The main exception is the `field-<field>` classes, which are intentionally not
namespaced in this fashion, as they are thought to be more applicable to the
particular use-case and less applicable to the dgrid components themselves.

In the overwhelming majority of cases, it is recommended to style using the
`.field-<field>` classes (or, if a `className` is specified in the column
definition, use that as it overrides the `.field-<field>` class).

### ColumnResizer: handle node class is now dgrid-resize-handle

The class on the resize handle node added to each header cell by the
ColumnResizer extension was formerly `dgrid-resize-handler`; this has been
corrected to `dgrid-resize-handle`.

## List

While these changes relate particularly to code in List.js, note that the changes
essentially affect all dgrid components, since all components extend from or
mix into List.

### new: get and set methods

Central `get` and `set` functions have been implemented, somewhat akin to the
interfaces seen in `dojo/Stateful` and `dijit/_WidgetBase`.  However, there are
some key differences:

* dgrid supports custom getters and setters, but they are named following the
  pattern of `_getFoo` and `_setFoo`, unlike Dijit's `_getFooAttr` and `_setFooAttr`.
* `watch` is not implemented.

Most `set*` functions found throughout dgrid components are now implemented
as custom setters, and should thus be accessed via the central `set` method.
For example, `setQuery(...)` is now `set("query", ...)`.  Deprecation stubs
are currently in place for the old APIs, but will be removed in the future.

### sortOrder property and sort function replaced by getter/setter

Previously, `sortOrder` was the (arguably internal) instance property used to
store the current sort options.  Sort code has since been rearranged; the new
recommended way to retrieve existing sort options is to call `get("sort")`.

Meanwhile, the `sort` method has been deprecated in favor of `set("sort", ...)`.
Sort order can also now be initially defined when creating a list or grid by
specifying a `sort` property in the object passed to the constructor.

## Grid

### columndef.get function now takes one parameter

The `get` function on column definitions is now passed only one argument: the
object for the row in question.

Earlier, the object was the second parameter, in order to match the signature of
the same function in dojox grid components.  However, the first parameter did
absolutely nothing in dgrid, and has now been removed.

## _StoreMixin (OnDemandList/OnDemandGrid, Pagination)

### new: columndef.set function

Store-backed grids now support a `set` function on the column definition object.
Like `get`, this function receives an object, which contains the updated item as
it will be `put` into the store.  The function may return a value to replace the
value in the field represented by the column.

Additionally, since the object passed to the function is the
object that will be `put`, it is possible to perform more complex
transformations by modifying the object directly; in this case, the function
may elect not to return anything.  Note, however, that this approach should
be used sparingly and carefully, since it is possible to do anything to the
item, and complications may develop if multiple columns in the same grid take
this approach.

### new: updateDirty

Store-backed grids also now have an `updateDirty(id, field, value)` method,
which can be used to update dirty state of items represented in the grid.
(On master this was previously known as `setDirty`, but did not exist in v0.2.)

## Selection / CellSelection

### dgrid-select and dgrid-deselect events

The behavior and signature of selection events has changed significantly.

* When a range is selected, instead of firing many individual events for each
  affected row/cell, a single batched event will be fired.
* These events now include a `rows` or `cells` property yielding an array of objects,
  rather than a `row` or `cell` property yielding a single object.
* Deselect events will now fire when rows are removed, or if a refresh occurs
  which resets the grid's selection.

### new: allowSelectAll property, disabled by default

Previously, checkbox selectors provided the ability to select all rows.
This ability is still provided, but is now determined by the value of the
`allowSelectAll` property.

Note, however, that this property defaults to `false`.  This feature is not
needed in all use cases, and its implications should be considered beforehand,
especially with regard to the lazy-loading nature of store-backed lists and grids.

Additionally, it is now possible to use Ctrl+A or Cmd+A to toggle between
selecting all items and selecting no items.

### new: allowSelect method

`Selection` now exposes an `allowSelect` method on the instance.  This method
receives a row object (or a cell object in the case of `CellSelection`) and
is expected to return `true` or `false`, reflecting whether selection of this
row or cell should be permitted.

This is particularly useful in conjunction with the selector column plugin,
which will display a disabled checkbox or radio button as appropriate.

### new: deselectOnRefresh property

Previously, the `Selection` module would clear the selection whenever a list
or grid is refreshed.  While this is still the default, the behavior can now
be disabled by setting `deselectOnRefresh` to `false`.

## selector

### columndef.type is now columndef.selectorType

In dgrid 0.2, the selector type (generally either `"checkbox"` or `"radio"`)
could be specified within the column definition object via the `type` property.
This has been changed to `selectorType` to avoid ambiguity.  The selector type
can also be specified as the second argument to the `selector` column plugin
function instead, as before.

## editor

The editor column plugin has been significantly refactored since v0.2.
The most notable changes in terms of API effects are noted below.

### widgetArgs property is now editorArgs

The `widgetArgs` property supported in the column definition by the editor
plugin has been renamed to `editorArgs` to be agnostic as to whether the
editor is a widget or a standard input, leaving the door open for usage with
standard HTML input types.

### editorArgs cannot be specified as a function

Previously, it was possible to specify `widgetArgs` as a function instead of an
object.  The function would receive a store item and be expected to return an
object hash to pass to the widget constructor each time an editor is rendered.

This capability was rarely useful, and is no longer viable, particularly due to
how editors now behave when `editOn` is specified: the editor component is only
constructed once, rather than every time a cell is activated for editing.

Thus, widget properties may only be specified directly via an object hash to
the `editorArgs` property.  For more advanced cases where the value needs to be
computed or transformed on a per-item basis, use the `get` function in the
column definition object to return the appropriate data.

### dgrid-datachange event properties

The `dgrid-datachange` event emitted by the editor column plugin now includes
a `cell` property, which contains the same data retrievable via
`grid.cell(event)`.  Since `grid.cell` is already called in the relevant
editor code, it is exposed directly on the event to avoid forcing developers
to perform the same lookup again on the other end.

Since it is possible to get cell and row information from this property,
the previously-exposed `rowId` property of the `dgrid-datachange` event is
now deprecated and will be removed in a future release.

The `dgrid-datachange` event also now includes a `grid` property containing a
reference to the Grid instance from which the event was fired.

## tree

### expand method added to grid instance

Tree columns now add an `expand(row, expand)` method to their parent grid,
for programmatically expanding or collapsing grid rows.  See the documentation
for details.

## DnD

### dndTargetConfig improved; is now dndParams

Previously, the DnD plugin defined a `dndTargetConfig` instance property, which
was a params object to be passed to the DnD Source constructor. However,
this was only used internally and did not consult any value provided via the
constructor.

This property has been renamed to `dndParams`, and now accepts an object value
via the constructor's arguments object.

### new: dndConstructor

Previously, the DnD plugin would always create an instance of the `GridSource`
constructor it defines and exposes.  A `dndConstructor` property has been added,
which can be used to specify an alternative DnD implementation to instantiate.

For best results, the constructor used should extend the `GridSource` constructor
exposed by the DnD module.

### default dndSourceType is now dgrid-row

The default value for the `dndSourceType` property has been changed from `row`
to `dgrid-row` to prevent ambiguity.

### DnD Source instance now stored as grid.dndSource

Previously, the DnD Source instance was stored on the grid instance under the
`dndTarget` property; this has been renamed more appropriately to `dndSource`.
