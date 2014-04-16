This document outlines changes since 0.3.0.  For older changelogs, see the
[dgrid wiki](https://github.com/SitePen/dgrid/wiki).

# master (0.3.15-dev)

## Significant changes

### Mixins

* The `Selection` mixin no longer emits superfluous `dgrid-deselect` events
  for rows which were already deselected. (#889)

### Extensions

* Fixed a regression in `ColumnHider` where the node to open the menu became
  invisible on platforms with hidden scrollbars. (#886)
* `ColumnHider` now assigns its menu node an ID in the format
  `{id}-hider-menu`, not `dgrid-hider-menu-{id}`.

## Other changes and fixes

### General/Core

* Fixed issues related to special characters in column IDs in `Grid`, `ColumnSet`,
  and the `ColumnHider` and `ColumnResizer` extensions. (#885)

# 0.3.14

## Significant changes

### General/Core

* Added a `List#addUiClasses` property which can be set to `false` on any
  instance to prevent it from adding `ui-` classes to various elements, which
  can help when using disparate jQuery UI and dgrid themes/skins on the same page.
  The option defaults to `true` for consistency with previous versions.
  Note that some selectors in various dgrid skins have been updated to not use
  `ui-` classes, to prevent undesired overriding of jQuery UI themes.  (#873)
* Added styles for a `dgrid-autoheight` class, which can be added to any list/grid
  via the `className` property to make the grid automatically size based on its
  contents.
* Fixed an issue where `List#destroy` would throw an error if `useTouchScroll` is
  set to `false` on a device with touch support. (#867)
* Fixed a regression in `List` which would cause observed modifications to tree
  children to throw errors. (#862)
* Fixed a regression in `OnDemandList` where items added to an empty list or
  grid would be inserted in the wrong position. (#840)
* Fixed ordering of inserted preload nodes in the linked list in `OnDemandList`,
  particularly affecting `tree`. (#817)
* `List#useTouchScroll` now defaults to `false` on platforms which render tangible
  scrollbars (namely, desktop browsers on touch-enabled devices such as the Surface).
* Fixed feature detection in `util/has-css3` to be more accurate and avoid causing
  errors in some situations. (#775)

### Mixins

* Fixed a regression in the `Keyboard` mixin which would cause errors when
  attempting to re-focus an updated row/cell when it (or the entire grid) is
  currently hidden. (#866)
* The `Selection` mixin will now listen for both touch and mouse events, rather
  than one or the other exclusively. (#757)
* The touch event(s) that `Selection` listens for can now be overridden via the
  `selectionTouchEvents` property. (#846)

### Extensions

* Fixed a regression in `CompoundColumns` involving the ability to look up
  columns by their originally-specified IDs. (#820)
* The `CompoundColumns` extension is now capable of interoperating with the
  `ColumnHider` and `ColumnResizer` extensions; note that it must be mixed in
  after these extensions in order to work properly. (#834)
* The `ColumnHider` and `Pagination` extensions now include Romanian localization
  bundles. (#850, thanks websoftix)

## Other changes and fixes

### General/Core

* Fixed an RTL issue that caused the column headers to misalign with the body
  on Chrome.

### Mixins

* Fixed issues in the `Selection` and `CellSelection` mixins when the row
  representing the starting point of a ranged selection is replaced (due to an
  observed store modification) prior to the end point being selected. (#858)
* The `ColumnSet` mixin no longer excludes touch devices when registering
  wheel listener logic (for combination mouse+touch devices).

### Column Plugins

* Fixed an issue in `editor` where the wrong column would be referenced from
  the `change` event handler for native inputs, particularly affecting radio
  buttons. (#876)

### Extensions

* Added logic to `ColumnHider` to skip hidden columns when calling `left` and
  `right` (which affects e.g. `Keyboard` navigation).
* Improved performance of first resize with `ColumnResizer`. (#832)
* Fixed errors in the `DnD` extension when using a mouse on a mouse+touch device.
* The `Pagination` extension will no longer cancel an ongoing async request if
  another call is performed with the same request promise. (#847, thanks jandppw)

# 0.3.13

## Significant changes

### General/Core

* `List#destroy` now resets `_started` to `false` to safeguard against debounced
  rendering-sensitive code running after the instance's DOM is no longer relevant. (#792)
* Added logic to account for `dojo/store/Observable`'s propensity to drop items
  at page boundaries, primarily in the `List` module. (#701, #714)
* Items added to stores which should appear at the end of a list or grid will now
  appear correctly. (#363)
* Fixed a long-standing regression in the `util/has-css3` module's
  `css-transforms3d` test due to a modified classname. (#776, thanks amuraco)

### Mixins

* Updated `Selection` to prefer `pointer` over `MSPointer` where available.
  This fixes ctrl+clicking behavior in IE11. Note that this change replaces the
  `has("mspointer")` feature with `has("pointer")`, which returns `"pointer"`,
  `"MSPointer"`, or `false`. (#794)

### Column Plugins

* The `expand` method added by the `tree` plugin will now return a promise,
  resolving after child data has loaded. (#739)
* The `canEdit` function supported by `editor` columns is now passed the proper
  up-to-date `value`. (#751)

### Extensions

* The `CompoundColumns` extension is now capable of interoperating with the
  `ColumnSet` mixin; see `test/extensions/CompoundColumns.html` for examples.
  (#383)

## Other changes and fixes

### General/Core

* Fixed an issue where `sort` would be ignored if it was a function with 0 arity,
  such as a hitched function being passed to a Memory store. (#771)
* Fixed an accessibility bug in non-Firefox browsers by only overriding
  `bodyNode.tabIndex` specifically for Firefox. (#823)
* Fixed a `loadingMessage` regression in `OnDemandList` which manifested
  particularly when `total` is not properly set in `QueryResults`. (#769)

### Mixins

* Fixed an issue in `Selection` and `CellSelection` which would cause errors when
  selecting very long ranges spanning beyond the currently-rendered rows in an
  OnDemandList. Note that while errors will no longer be thrown, the selection
  range will still be reset. (#705)

### Extensions

* The `Pagination` extension now includes an Arabic localization bundle.
  (#770, thanks elombashy)

# 0.3.12

## Significant changes

### General/Core

* Fixed a regression in `Grid` since 0.3.7 where formatters were run in the
  global context by default instead of in the context of the column definition.
  (#748, thanks mbretter)
* The `className` column definition property now supports being assigned a
  function value, in which case the function will be called for each row in the
  grid (including the header).  For rows in the body, the associated data object
  (e.g. store item) will be passed, but for the header row, nothing will be
  passed, so this will need to be handled in the function's logic.

### Mixins

* `Selection` and `CellSelection` now fire `dgrid-select` and `dgrid-deselect`
  events on the same turn that `select` is called. The events still include
  `rows` or `cells` containing all rows or cells selected at once; only the
  timing of the events firing has changed.
* Fixed an issue in `Selection` code flow which caused devices supporting
  MSPointer to behave incorrectly with recent versions of Dojo.

### Extensions

* Fixed a regression in `Pagination` where `rowsPerPage` (and thus also
  `queryOptions.count`) would be set to a string rather than a number when the
  page size drop-down is used. (#752)

## Other changes and fixes

### Mixins

* The `Keyboard` mixin now properly adds/removes header navigation when
  `set("showHeader", ...)` is called. (#734)

### Column Plugins

* Added logic to `editor` to preserve editor focus when a row is updated
  (particularly useful with always-on editors with autoSave enabled). (#579)
* Removed a `mousedown` event handler from `editor` which was interfering with
  certain widget features such as `TextBox#selectOnClick`; this event handler
  should no longer be necessary. (#704)

### Extensions

* The `ColumnHider` extension's menu trigger node no longer reopens the menu if
  the menu is already open; it will close it just like clicking anywhere else
  outside the menu. (#755)

# 0.3.11

## Significant changes

### General/Core

* Fixed a regression related to `OnDemandList` in conjunction with the `tree`
  plugin, where queries would not fire due to confusion between different levels.
  (#717)
* Fixed a regression related to `List` and `OnDemandList` in conjunction with
  `tree` by adding a `cleanEmptyObservers` flag, which `tree` will set to false.
  (#713)
* Added a `highlightDuration` property to `List` to allow customizing the length
  of time that rows remain highlighted when modified. (#736, thanks Zarillion)

### Mixins

* Fixed a follow-up issue in `Selection` related to the fix for #226, where
  deselect events were not firing for removed rows. (#684)

### Column Plugins

* The `tree` column plugin will now include an `originalQuery` property in the
  `options` object passed to `getChildren`, allowing store implementations to
  re-apply query filters to queries for child items. (#145, #732)

### Extensions

* The `Pagination` extension now has proper setters for `rowsPerPage` and
  `pageSizeOptions`.  If `rowsPerPage` is set to a value that is not present in
  `pageSizeOptions`, an option will be added for the new value.  The drop-down's
  options will always appear in ascending order. (#631)

## Other changes and fixes

### General/Core

* Fixed an issue in `OnDemandList#_calcRowHeight` to properly calculate height
  of the first row. (#552)
* Fixed a compatibility issue in `OnDemandList` and `dojo/store/DataStore` due
  to a conflicting property in `queryOptions`. (#440)

### Mixins

* Fixed an issue in `Selection` where its select-all keybinding would prevent
  select-all functionality within text editors. (#711)
* Fixed an issue in `Selection` where the selection could fall out of sync for
  an item with a falsy id. (#715)

### Extensions

* The `Pagination` extension will now render its footer controls properly in RTL
  locales (provided `dgrid_rtl.css` is loaded). (#707)

# 0.3.10

## Significant changes

### General/Core

* Updated the README and fixed the redirect in `test/intern/runTests.html` to
  reference the correct path where intern-geezer installs to as of Intern 1.2.
* Fixed some issues, including a regression, in `List` involving handling of
  observed store updates, particularly in conjunction with overlapping queries
  performed by `OnDemandList`. (#701)
* Fixed a regression in `_StoreMixin` (affecting `OnDemandList` and `Pagination`)
  where setting `store` to `null` would cause an error. (#688, thanks kilink)
* Fixed a regression in `_StoreMixin` which caused an error when updating the
  only row present in a list or grid. (#693)
* Updated the `put-selector` dependency to 0.3.5, which includes a fix for an
  issue involving iOS Safari's JavaScript optimization, which was causing
  errors in dgrid.

## Other changes and fixes

### Mixins

* The `Keyboard` mixin will now manage focus if a row is updated or removed;
  in the former case, the new row will receive focus (assuming it is within
  the currently-rendered area), otherwise the next row will receive focus. (#496)
* The `editor` column plugin will now return focus to the parent cell when an
  editor is dismissed, if the `Keyboard` mixin is also in use. (#263)

### Extensions

* Improved accessibility of the `ColumnHider` extension, adding a tab stop for
  the menu trigger, focusing the first checkbox within the menu when it opens,
  allowing it to be dismissed by pressing escape (at which time focus returns
  to the trigger), and adding ARIA role and label to the popup menu itself.

# 0.3.9

## Significant changes

### General/Core

* dgrid now uses [Intern](http://theintern.io) for unit and functional tests,
  instead of DOH.  See the README for setup instructions.
* Fixed a regression with `OnDemandList` which would cause improper rendering
  after scrolling. (#548)
* Fixed an issue with `OnDemandList` causing `queryRowsOverlap` only taking
  effect between the first two queries. (#644)
* Added the capability to opt out of custom TouchScroll logic on devices that
  support touch, by setting `useTouchScroll: false` on the instance. (#656)
* Fixed logic in `Grid`, `GridFromHtml`, and `selector` to allow specifying a
  blank label for a column by passing an empty string to `column.label`. (#664)

### Mixins

* The `Selection` mixin now uses MSPointer events where available, which avoids
  issues in cases where something cancels a MSPointer event, preventing relevant
  mouse events from firing (for example, `dojo/dnd` + `dojo/touch` in 1.9). (#658)
* The `CellSelection` mixin now supports selecting or deselecting all columns
  in a row if a row object is passed.
* Fixed a regression in the `Selection` mixin where unselectable rows could still
  be selected via ctrl+click.

### Column Plugins

* Fixed a regression in `selector` which caused an error when clicking the
  select-all checkbox. (#674)

### Extensions

* Fixed a regression in the `Pagination` extension where duplicate rows could
  be displayed if several paging/sorting requests are fired in quick succession
  to an asynchronous store.  Note that the fix involves canceling old requests,
  which may cause Deferred errors to be logged to the console; this is normal.
  The `dgrid-error` event will *not* be emitted for canceled requests. (#635)

## Other changes and fixes

### General/Core

* Fixed a potential issue in `Grid` in non-ES5 environments that augment the
  Array prototype. (#624)
* Fixed an issue with `OnDemandList` involving where a new row is inserted in
  the DOM when the relevant result set is currently empty. (#647)
* Fixed issues involving `List` and `OnDemandList` not properly cleaning up
  observers that are no longer needed. (#642, #677)
* Reworked logic in `List#adjustRowIndices` to not skip updating row indices
  even when `maintainOddEven` is `false`.
* Fixed an edge case in `OnDemandList` where it would refuse to load additional
  data if the grid were resized larger while its viewport is scrolled to the top.
  (#361)

### Mixins

* Fixed an issue in the `ColumnSet` mixin which affected horizontal scrolling at
  certain zoom levels on Chrome.
* The `Selection` and `CellSelection` mixins no longer lose selection of rows
  when items are modified.  Rows are still deselected if items are removed.
  (#226)

### Column Plugins

* Fixed issues in the `editor` column plugin regarding consistency of
  dirty data and `dgrid-datachange` event firing for always-on radio buttons.
* Fixed an issue in the `editor` plugin that caused errors in Chrome/Safari when
  an editor loses focus and hides due to clicking within the browser's UI
  controls. (#603)
* Fixed an issue in the `editor` column plugin's cleanup logic which could occur
  when the loading node for a request is removed before the request completes.
  (#195)
* The `editor` column plugin will now directly update row data in cases where
  a store is not being used. (#171)

### Extensions

* Fixed an issue with the `ColumnReorder` extension involving grids whose IDs
  end with a hyphen followed by numbers. (#556)
* The `ColumnResizer` extension now properly calls the grid's `resize` method,
  even on programmatically-triggered resize operations.
* Fixed a potential issue in the `CompoundColumns` extension in non-ES5
  environments that augment the Array prototype. (#624)
* Added localizations for the `Pagination` extension:
  * German (#657, thanks tryte)
  * Traditional and Simplified Chinese (#671, thanks expando)
  * Thai (#672, thanks dylans)

# 0.3.8

## Significant changes

### General/Core

* The `dgrid-sort` event now emits off of the original target of the event which
  triggered it, rather than always off of the header cell. (#539)
* Fixed a regression (present since 0.3.5) in `OnDemandList` which prevented
  `noDataMessage` from being displayed for async stores. (#519)
* `_StoreMixin` (used by `OnDemandList`, `OnDemandGrid`, and `Pagination`) now
  supports calling the `set` method of Stateful objects during `save`.  (#563)

### Column Plugins

* Resolved an infinite-recursion regression in `selector`, observable when used
  in conjunction with the `ColumnReorder` extension. (#525)

### Extensions

* Fixed a regression in the `ColumnResizer` extension where columns were no
  longer appropriately adjusted when the first resize occurred. (#526)

## Other changes and fixes

### General/Core

* Fixed issues in `OnDemandList` and the `Pagination` extension where
  `noDataMessage` could potentially appear multiple times for successive
  empty query results. (#542)

### Mixins

* Resolved an issue in the `ColumnSet` mixin which caused some browsers to block
  clicks near the bottom of the grid when no ColumnSet scrollbars are shown.
  (#571)

### Column Plugins

* Resolved an issue in `selector` where selectors would not work in cases where
  the initial column structure did not contain a selector column, but the
  structure was later changed to include one. (#533)
* Resolved an issue in `selector` where rows that should be unselectable were
  still selectable by clicking within the selector column. (#545)

### Extensions

* Revised the previous workaround for IE8 in the `ColumnHider` extension to
  an alternative which involves less code and avoids an issue when all columns
  are hidden. (#537)
* The `DijitRegistry` extension now implements the `isLeftToRight` method, to
  accommodate needs of Dijit layout widgets in Dojo 1.9. (#536)
* The `DijitRegistry` extension now implements the `getParent` method, to
  accommodate e.g. `dijit/_KeyNavContainer`. (#538, thanks k2s)
* The `Pagination` extension now properly only shows page 1 once if there is
  only one page of results. (#520)
* The `Pagination` extension now properly initializes the page size drop-down
  based on the initial `rowsPerPage` value, if one matches.
  (#577, thanks Gordon Smith)

# 0.3.7

## Significant changes

### General/Core

* `Grid` now supports the `formatterScope` instance property, along the same
  lines as `dojox/grid`. (#470; thanks gratex)
* `Grid` has been refactored to include `formatter` considerations within the
  default `renderCell` logic; this allows `formatter` functions to coexist with
  the `editor` and `tree` column plugins. (#495, #497; thanks gratex)
* Fixed an issue with `_StoreMixin` which caused `set` functions in column
  definitions to be ignored for all but the last subrow or columnset. (#489)

### Mixins

* Fixed a regression in the `Selection` mixin due to text selection changes,
  where Firefox would not allow selecting text or moving the cursor inside
  form inputs. (#492)
* The `Selection` mixin no longer calls `allowSelect` for `deselect` calls
  (only `select` calls).  This avoids potential errors when resetting column
  structures, and reduces unnecessary calls.
* The `Selection` mixin has been refactored to break out logic for each selection
  mode to a separate method.  These methods follow the naming convention
  `_modeSelectionHandler` (where "mode" would be the name of the mode).
  This allows custom selection modes to be added easily.
* The `Selection` mixin now supports a `toggle` mode, useful for touch input
  where holding a modifier key to deselect is generally not an option.
* Fixed an issue with the `Selection` and `CellSelection` mixins where calling
  `deselect` with a range would actually deselect the first target, then select
  everything else in the range. (#491)

### Column Plugins

* The `selector` plugin will now match its disabled state against the
  `allowSelect` method on the grid, as well as the column definition's
  `disabled` function.
* The `tree` plugin's `renderExpando` function now receives a 4th argument:
  the object represented by the current row. (#427; thanks pags)

### Extensions

* The `ColumnResizer` extension no longer emits superfluous events for all columns
  on the first resize. (#441)
* The `DnD` extension now inherits the `Selection` mixin to guarantee resilient
  handling of drag operations where part of the selection has scrolled out of
  view and been unrendered.
* The `Pagination` extension now applies the `dgrid-page-link` class to all
  navigation controls (not just the page numbers), to make them distinguishable
  by something other than what tag they use. (related to #379)

## Other changes and fixes

### General/Core

* The `List` module's `startup` method now correctly checks `_started` before
  calling `this.inherited`.  (Thanks dancrumb)
* Fixed an issue in `List` which could cause errors on certain successive tree
  row removals/insertions. (#418, #467)

### Mixins

* The `ColumnSet` mixin now adjusts the positioning of its scrollbars
  appropriately if the footer node is present. (#463)
* The `CellSelection` mixin now properly deselects if an unselected cell within
  the same row as a selected cell is right-clicked.
* Fixed issues with the `Keyboard` mixin pertaining to resetting columns, or
  not setting them initially. (#494)
* The `Keyboard` mixin now ensures that if the header area is scrolled due to a
  focus shift, the body scrolls with it. (#474)

### Column Plugins

* Fixed an issue in the `editor` plugin that caused checkboxes to fail to
  initialize values properly in IE < 8. (#479)
* The `tree` plugin no longer completely overwrites classes on the expando node
  when expanding/collapsing, so custom classes will be preserved. (#409)

### Extensions

* The `ColumnHider` extension now absolutely-positions the node for opening the
  menu, which ensures it is visible even on platforms with no vertical scrollbars.
  (#406)
* The `ColumnHider` extension now relies on CSS to specify an icon, rather than
  using text to show a plus sign.  The icon can be changed by overriding
  the background on the `dgrid-hider-toggle` class.  (#306)
* Fixed issues in the `ColumnHider` extension involving redundant calls to
  `toggleColumnHiddenState`. (#464)
* The `DnD` extension now cleans references from the dnd source's hash when
  `removeRow` is called on the grid. (#335)
* Resolved an issue in `Pagination` where IE9+ would dispatch events to the
  wrong handlers after clicking one of the navigation controls. (#379)

# 0.3.6

## Breaking changes

### OnDemandList's dgrid-refresh-complete event no longer includes rows

The `rows` property of this event was removed to match the implementation
added to the Pagination extension, which does not include it.  If a particular
row is needed, it can be resolved from the QueryResults included on the event
via `grid.row(...).element`.

## Significant changes

### General/Core

* Added an index page to the test folder to browse the tests via a grid. (#407)
* Added a preliminary set of DOH tests to assist in spotting regressions. (#412)

### Mixins

* The `Keyboard` mixin has been made significantly more extensible (#429):
  * Added `keyMap` and `headerKeyMap` properties, which are object hashes
    whose keys are event key codes and whose values are functions to be
    executed in the context of the instance; if not specified, defaults
    (exposed via `Keyboard.defaultKeyMap` and `keyboard.defaultHeaderKeyMap`)
    will be used.
  * Added `addKeyHandler(key, callback, isHeader)` method for registering
    additional keyboard handlers; this is usually easier than trying to
    override `keyMap` or `headerKeyMap`.
* The `Keyboard` mixin no longer emits `dgrid-cellfocusout` and
  `dgrid-cellfocusin` when spacebar is pressed. (#429)

### Column Plugins

* The `editor` column plugin now emits `dgrid-editor-show` and `dgrid-editor-hide`
  events when an editor with `editOn` set is shown or hidden, respectively. (#424)
* The `editor` column plugin now adds a `dgrid-cell-editing` class to any cell
  containing an active editor. (#442; thanks Brandano for the idea)

### Extensions

* The `Pagination` extension now emits `dgrid-refresh-complete` like
  `OnDemandList`.  (#188, #411)

## Other changes and fixes

### General/Core

* Fixed `Grid#styleColumn`, which had broken in 0.3.5. (#408)
* Fixed an issue with `Grid#cell` specific to when a cell object representing a
  header cell was passed in. (#429)
* The `Keyboard` mixin now properly handles Home/End keypresses.
* Fixed logic in `_StoreMixin` to work around a
  [Dojo 1.8 bug with `when`](http://bugs.dojotoolkit.org/ticket/16667), which
  could inappropriately mutate the return value of `_trackError`. (#411)
* Fixed logic in `OnDemandList` so that asynchronous errors during `refresh`
  are properly signaled via the promise it returns. (#411)
* Added CSS to ensure that IE6 renders empty `OnDemandList` preload nodes with
  0 height. (#429)

### Column Plugins

* The `editor` plugin now supports widgets returning object values by comparing
  using `valueOf`. (#256, #304, #423)
* The `tree` plugin has been refactored to make use of the `util/has-css3`
  module, rather than feature-detecting upon first expansion. (#416)
* The `tree` plugin now implements `expand` such that it will bail out if the
  target row is already in the desired state.

# 0.3.5

## Breaking changes

### Signature of the newRow method

The `newRow` method in List, called in reaction to observed store changes,
has had its signature altered to match that of `insertRow`.  Please note
that it is likely that `newRow` may be refactored out of existence in the future.

### Grid and the columns property

The `Grid` module now normalizes the `columns` instance property to an object
even when it is passed in as an array. This means that any code written
which accesses `grid.columns` directly will break if it expects it to maintain
the array structure that was originally passed in.

To compensate for this, `get("columns")` retains the previous behavior - it
returns `columns` as initially passed, except in the case where `subRows` is
passed instead, in which case it returns an object hash version of the structure
keyed by column IDs.

### put-selector version

When updating to dgrid 0.3.5, make sure you also update your version of
[put-selector](https://github.com/kriszyp/put-selector) to 0.3.1 or higher
(0.3.2 is the latest at the time of this writing).  If you use
[cpm](https://github.com/kriszyp/cpm) to update dgrid, this should happen
automatically.

## Significant changes

### General/Core

* `List` instances will now clean up any styles added dynamically via the
    `addCssRule` method; this also applies by extension to `Grid#styleColumn`
    and `ColumnSet#styleColumnSet`.  This may cause a change in behavior in some
    edge cases; the previous behavior can be obtained by passing
    `cleanAddedRules: false` in the constructor arguments object. (#371)
* The `up` and `down` methods of `List` will now call `grid.row` internally to
    resolve whatever argument is passed; the `left` and `right` methods of
    `Grid` will call `grid.cell`.  (Formerly these methods only accepted a
    row or cell object directly.)
* The `Grid` module now ensures that an object hash of the grid's columns is
    always available (see Breaking Changes above); this fixes issues when
    column IDs are explicitly set, but then couldn't be properly looked up
    against the `columns` array.
* The `Grid` module now emits a `dgrid-sort` event when a sortable header cell
    is clicked; this event includes a `sort` property, and may be canceled to
    stop the sort, or to substitute alternative behavior.  In the latter case,
    if updating the sort arrow in the UI is still desired, call the
    `updateSortArrow` method and pass the `sort` value from the event.
* The `OnDemandList` module now supports a `pagingMethod` property, which allows
    specifying whether to throttle or debounce scroll events.  The default
    behavior has been changed from `"throttleDelayed"` to `"debounce"`, which
    generally is capable of far reducing the number of store queries issued,
    moreso if `pagingDelay` is increased (though its default remains the same).
* The `OnDemandList` module now supports a `keepScrollPosition` property, which
    will attempt to preserve scroll position between refresh calls.  This can be
    set on the instance itself to affect all refreshes, or can be passed to the
    `refresh` method directly for a specific call.
* The `OnDemandList` module now returns a promise from the `refresh` method,
    which resolves when the grid finishes rendering results after the refresh.
    It also emits a `dgrid-refresh-complete` event, which includes both a
    reference to the QueryResults object (`results`) and the rendered rows
    (`rows`).  In addition, the `dgrid-error` event now fires more consistently
    (both for `OnDemandList` and `Pagination`).

### Mixins

* The `Selection` mixin now supports an `allowTextSelection` property, allowing
    text selection within a List or Grid to be permitted or denied completely
    independently from the `selectionMode` property; default behavior is still
    to prevent unless `selectionMode` is `none`.  Selection prevention itself
    has also been fixed to work in all browsers. (#148)

### Column Plugins

* Fixed a `tree` regression since 0.3.2 involving only-child rows being misplaced
    upon observed changes. (#353)

### Extensions

* The `ColumnResizer` extension now supports an `adjustLastColumn` flag; when
    set to `true` (the default, and previous behavior), this will adjust the
    last column's width to `auto` at times where a column resize operation would
    otherwise cause column widths to stretch due to how browsers render tables.
    This can be set to `false` to purposely disable this behavior.
* The `Pagination` extension now returns a promise from the `refresh` and
    `gotoPage` methods, which resolves when the grid finishes rendering results.
    Note that it does not (yet) emit an event like `OnDemandList`.
* The `Pagination` extension now re-queries for the current page of data when
    the grid is notified of a store modification which affects the number of
    items currently rendered. (#283)
* The `Pagination` extension now supports a `showLoadingMessage` property; by
    default (`true`), a loading node will be displayed whenever a new page is
    requested; if set to `false`, the grid will instead retain the previous
    content until the new data is fully received and ready to render. (#219)
* The `Pagination` extension now includes localized strings for the following languages:
    * French (#381, thanks mduriancik)
    * Brazilian Portuguese (#376, thanks stavarengo)
    * Slovak (#381, thanks mduriancik)
* The `DijitRegistry` extension now supports dgrid components as direct children
    of common Dijit layout container widgets, and will now properly alter the
    size of a list or grid if the `resize` method is passed an argument. (#401)

## Other changes and fixes

### General/Core

* Resolved an issue where upon changing column structure, the placement of the
    sort arrow would be lost even though the grid is still sorting by the same
    field.
* Simplified logic in `Grid` to always create `tr` elements. (#387)
* Resolved an issue where `OnDemandList` could end up firing requests where
    start exceeds total and count is negative. (#323)
* Resolved issues regarding proper handling of errors / rejected promises in
    `OnDemandList` as well as the `Pagination` extension.
    (#351; obsoletes #241, #242)
* Resolved potential memory leaks in `Grid`, `ColumnSet`, and `ColumnResizer`.
    (#393, #394, #395, #396, #397)
* Resolved issues in `Grid`, `ColumnSet`, `ColumnHider`, and `ColumnResizer`
    regarding dynamic style injection for grids with DOM node IDs containing
    unsafe characters; added `escapeCssIdentifier` function to `util/misc`. (#402)
* Resolved an issue in `TouchScroll` which unnecessarily prevented native
    touch-scrolling even when the component can't be scrolled. (#344)

### Mixins

* Resolved an issue with the `ColumnSet` mixin where clicking within the
    horizontal scrollbar area (aside from the arrows/handle) wouldn't work in IE.
    (#307)
* Improved logic of `isSelect` for `Selection` and `CellSelection` regarding
    unloaded rows/cells in combination with the select-all feature in some cases.
    (#258)

### Extensions

* Resolved an issue where `ColumnHider` would leave styles applied for hiding
    columns, which could have adverse effects if a new grid is later created
    with the same ID. (#371)
* Resolved an issue with `ColumnHider` which could cause the hidden state of
    columns to be forgotten when other components such as `ColumnReorder`
    interact with the column structure. (#289)
* Resolved an issue with `ColumnHider` related to IE8 standards mode's handling
    of `display: none` cells. (#362)
* Resolved an issue where widths set via the `ColumnResizer` extension would be
    reset upon rearranging columns with the `ColumnReorder` extension.
* Resolved an issue in `ColumnResizer` styles which caused body and header cells
    to skew in Chrome 19 and Safari 6. (#142, #370)
* Changed name of private `_columnStyles` object used by the `ColumnResizer`
    extension to `_columnSizes` to reduce ambiguity.
* The `Pagination` extension will no longer immediately throw errors if it is
    initialized without a store.  However, a warning will be logged, and any
    method calls will likely throw errors until a store is assigned. (#355)

# 0.3.4

## Significant changes

### Extensions

* The `ColumnResizer` extension now emits a `dgrid-columnresize` event when a resize
    occurs; if initiated by the user, the event will include a `parentType` property
    indicating the type of event that triggered it.  If this event is canceled,
    the column will not be resized. (#320)
* The `ColumnResizer` extension now honors a `width` property included on column
    definition objects for the purpose of initializing the width of a column; this
    can be useful if it is desired to persist and restore custom column widths
    from a cookie or other local storage. (#321)
* The `ColumnResizer` extension now honors a `resizable` property included on
    column definition objects for the purpose of disallowing resize of specific
    columns. (#325)

## Other changes and fixes

### General/Core

* Resolved an issue in `List` relating to scrolling and preload nodes. (#318, #323)

### Mixins

* The `ColumnSet` mixin now supports horizontal mousewheel events. (#239)

### Column Plugins

* The column plugins (`editor`, `selector`, and `tree`) can now be invoked without
    a column definition object at all, if no properties need to be set.  This
    is mostly useful for `selector`. (#324)
* Fixed an issue with the `selector` plugin when a column definition lacks a
    `label` property. (#324)
* Always-on `editor` columns now honor the `canEdit` function on column definitions
    at the time each cell is rendered.
* Always-on `editor` columns now properly revert values if the `dgrid-datachange`
    event is canceled. (#252)

### Extensions

* The `ColumnResizer` extension's resize indicator now follows the cursor
    even when dragging beyond the grid's boundaries, and reacts if the mouse
    button is released even outside the boundaries of the browser window. (#310)

# 0.3.3

## Breaking changes

* The `Keyboard` module's `dgrid-cellfocusin` and `dgrid-cellfocusout` events
    now report either a `row` or `cell` object, depending on whether
    `cellNavigation` is `false` or `true`, respectively.  (Formerly these events
    always contained a `cell` property pointing to the DOM node that fired the event.)
* Several mixin and extension modules have had their `declare` hierarchies
    simplified under the expectation that they will always be mixed in as
    documented, and never be instantiated directly.  To be clear, this will not
    break any code that is written as prescribed by the documentation.

## Significant changes

* All custom events fired by dgrid components now report the following properties:
    * `grid`: The dgrid instance which fired the event.
    * `parentType`: If the event was fired in direct response to another event,
        this property reflects the type of the originating event.  If the event
        was fired due to a direct API call, `parentType` will not be defined.
* The `ColumnReorder` extension now fires a `dgrid-columnreorder` event when
    a column is reordered via drag'n'drop.  Note that this event always reports
    a `parentType` of `"dnd"` (there is no way to trigger this event directly
    from an API call).
* The `Pagination` extension now exposes and references its i18n strings via the
    `i18nPagination` instance property, allowing these strings to be overridden.
    (#225)

## Other changes and fixes

### General/Core

* Fixed an issue with the `up` and `down` methods in `List` and the `left` and
    `right` methods in `Grid`, which could cause them to attempt to traverse
    outside the list/grid in question.
* Fixed an issue in the observer code in `List` which could cause an updated
    row to render out-of-sequence when `tree` is used. (#154)
* Fixed an issue that could cause old IE to throw errors due to an undefined
    parameter to `insertBefore`. (#308)
* The `_StoreMixin` module now shows/hides a node displaying `noDataMessage` in
    reaction to the last row being removed or first row being added. (#229)
* The `OnDemandList` module now adheres more strictly to the `maxRowsPerPage`
    property.  To accommodate this, the default has been increased from `100` to
    `250`. (#280)
* The `OnDemandList` module's default value for `farOffRemoval` has been
    lowered from `10000` to `2000`.
* The `loadingMessage` property (referenced by `OnDemandList` and the `Pagination`
    extension) now supports HTML strings, like `noDataMessage` (#312)
* The CSS for one of the `util/has-css3` module's tests has had its class renamed
    to prevent conflicting with users of Modernizr. (#313)

### Mixins

* The `Selection` mixin in single-selection mode now properly allows reselecting
    a row that was deselected immediately prior. (#295)

### Extensions

* The `ColumnHider` extension will now resize its popup element and enable
    scrolling within it, in cases where its height would otherwise exceed the
    that of the parent grid. (#311)
* The `Pagination` extension now supports `noDataMessage` like `OnDemandList`. (#180)

# 0.3.2

## Breaking changes

### GridFromHtml and OnDemandGrid

The `GridFromHtml` module no longer automatically mixes in the `OnDemandGrid`
module, mixing in only `Grid` instead, in order to support the option of using
alternative store-backed mechanisms such as the `Pagination` extension.
This may cause existing code which relied on `GridFromHtml` and loaded from a
store to break.  Such cases will now need to mix in `OnDemandList` manually
(they don't need to mix in `OnDemandGrid`, since `Grid` is still inherited by
`GridFromHtml`).

There are a couple of ways to deal with this.  In Dojo 1.8, when parsing dgrid
instances declaratively, the new `data-dojo-mixins` attribute can be used to
mix `OnDemandList` into `GridFromHtml`:

```html
<table data-dojo-type="dgrid/GridFromHtml" data-dojo-mixins="dgrid/OnDemandList" data-dojo-props="...">
    ...
</table>
```

In the case of Dojo 1.7, `dojo/parser` doesn't understand module IDs, and so a
global reference to the dgrid components used is needed.  Changing such code to
mix in `OnDemandList` involves nothing more than an additional use of `declare`:

```html
<table data-dojo-type="dgrid.OnDemandGridFromHtml" data-dojo-props="...">
    ...
</table>
...
<script>
    var dgrid = {}; // declared in global scope
    require(["dojo/_base/declare", "dojo/parser", "dgrid/GridFromHtml", "dgrid/OnDemandList", ..., "dojo/domReady!"],
    function(declare, parser, GridFromHtml, OnDemandList, ...) {
        // Create dgrid constructor with necessary components, available in the global scope.
        dgrid.OnDemandGridFromHtml = declare([GridFromHtml, OnDemandList]);
        
        // Parse the document, now that the above constructor is available.
        parser.parse();
    });
</script>
```

## Significant changes

### General/Core

* All dgrid components now have `scrollTo` and `getScrollPosition` methods,
  either inheriting from `TouchScroll` (see below) or implemented in `List`
  based on `scrollTop` and `scrollLeft`.  Updates have been made to dgrid
  components where necessary to leverage these methods.
* All dgrid components now respond to `set("showFooter")` consistently with
  `set("showHeader")`. (#284)
* It is now possible to initialize or later set CSS classes on a dgrid component's
  top DOM node via `"class"` or `className`. (#183)
* `_StoreMixin` (used by `OnDemandList` and the `Pagination` extension) now
  includes a reference to the grid instance in emitted `dgrid-error` events
  (via a `grid` property on the `error` object).
* The `TouchScroll` module has undergone significant changes and improvements:
    * uses CSS3 `translate3d` to take advantage of hardware acceleration
        * a `util/has-css3` module has been added with has-feature tests to
          detect CSS3 features to be used by `TouchScroll`
    * implements increased tension and bounce-back beyond edges
    * displays scrollbars as appropriate while scrolling
    * implements `scrollTo` and `getScrollPosition` methods to allow manipulation
      and retrieval of scroll information based on CSS transformations
    * allows configuring how many touches are necessary to activate scrolling,
      via the `touchesToScroll` property

### Mixins

* The `ColumnSet` mixin now defines a `styleColumnSet` method, which is
  analogous to Grid's `styleColumn` method, but instead adds a style rule for
  the class on nodes containing the entire columnset contents for a row.
* The `Keyboard` mixin now defines `focus` and `focusHeader` methods, for
  programmatically focusing a row or cell (depending on the value of the
  `cellNavigation` setting). (#130)

### Column Plugins

* The `tree` column plugin now supports a `collapseOnRefresh` property in the
  column definition; if set to `true`, it will cause all parent rows to render
  collapsed whenever the grid is refreshed, rather than remembering their
  previous state.
* The `tree` column plugin now supports a `allowDuplicates` property in the
  column definition; this can be set to `true` to allow for cases where the same
  item may appear under multiple parents in the tree.  Note however that it
  limits the capabilities of the `row` method to the top level only. (#147)

### Extensions

* A `CompoundColumns` extension has been added, which allows defining column
  structures which include additional spanning header cells describing the
  contents beneath.
* The `ColumnHider` extension has undergone some refactoring to make it more
  extensible and to provide a public API for toggling the hidden state of a
  column, via the `toggleColumnHiddenState(columnId)` method.
* The `ColumnReorder` extension has been refactored to allow reordering of
  columns within the same subrow or columnset in more complex column structures,
  in addition to the previous ability to reorder columns in simple single-row
  structures.
* The `DnD` extension now properly supports touch devices when used with Dojo 1.8.
* The `DnD` extension now supports specifying a `getObjectDndType` function, for
  customizing the DnD type reported for each item rendered.

## Other changes and fixes

### General/Core

* Several accessibility issues have been addressed, including fixes to the
  roles reported by certain elements, and labels added to the Pagination
  extension's controls. (Partly attributed to #273)
* `Grid`: calls to `cell` with a falsy `columnId` value now work properly. (#198)
* Fixed an issue with dgrid instances not reacting correctly to window resize.
* Fixed an issue affecting odd/even row classes on in-place updates. (#269)
* Fixed a rendering issue involving confusion of preload node dimensions. (#161)
* Fixed an issue causing `tree` level indentation to render improperly when used
  with the `Pagination` extension.
* Fixed a deprecated API call in `_StoreMixin`. (#272)
* Improved logic in `OnDemandList` to properly account for lists with displays
  which tile items using `display: inline-block`.

### Mixins

* The `ColumnSet` mixin now behaves properly when calling
  `set("columnSets", ...)`. (#202)
* The non-standard `colsetid` attribute assigned to nodes by the `ColumnSet`
  mixin has been replaced with the `data-dgrid-column-set-id` attribute.
* The `Selection` mixin will now properly reset `_lastSelected` when
  `clearSelection` is called. (#175)
* The `Selection` mixin will now wait until `mouseup` when handling mouse events
  on targets that are already selected. (#251)

### Column Plugins

* The `expand` method defined by the `tree` column plugin will no longer
  be called at all in reaction to events on rows which report no children.

### Extensions

* The `ColumnHider` extension now supports setting `hidden` and `unhidable`
  together, resulting in the column being hidden and not being present in the
  popup menu (but it can still be shown programmatically). (#199)
* The `ColumnHider` extension now behaves appropriately for columns with no
  `label` defined. (#244)
* A number of protected members in the `ColumnHider` extension have been renamed:
    * `_toggleColumnState` has been replaced by `_setColumnHiddenState` and the
      public API `toggleColumnHiddenState` mentioned above
    * `_toggleHiderMenu` has been renamed to `_toggleColumnHiderMenu`
    * `_columnStyleRules` has been renamed to `_columnHiderRules`
* An issue with the `ColumnResizer` extension which could cause distortion of
  width values on the first resize has been fixed. (#291)
* The `DnD` extension can now drag non-root tree items *in Dojo 1.8 only* by
  passing `allowNested: true` to the source via `dndParams`. (#68)
* The `DnD` extension now behaves better with regard to synchronizing with
  dgrid's `Selection` mixin, and also with regard to dragging when some selected
  nodes are no longer in the DOM. (#185, #246)
* The `DnD` extension now adds CSS to adequately override spurious styles which
  can leak in from dijit.css in Dojo 1.8. (#255)

# 0.3.1

## Significant changes

* Column plugins can now define the following functions on column definitions,
  providing more opportune timing for initialization and tear-down:
    * `init`, which will be executed at the time the grid's column configuration
      is (re-)applied
    * `destroy`, which will be executed when the grid is destroyed, as well as
      before a new column configuration is applied
* The `tree` plugin now supports the following column definition properties:
    * `shouldExpand(row, level, previouslyExpanded)`, a function providing for
      conditional automatic expansion of parent rows (#141)
    * `indentWidth`, an integer specifying the size (in pixels) of each level's
      indent (note that the default is now `9`, though it was previously `19`)
    * `renderExpando()`, a function which can replace the default logic for
      rendering the expando node (the arrow next to the content of each cell)
* The `editor` plugin now augments the grid instance with an `edit(cell)` method
  which can be used to programmatically activate the editor in a given cell.
* A `util/mouse` module has been added, which exposes simulated events for
  the mouse entering and leaving grid rows and cells. (#165)
* A `package.js` has been added in order to streamline the build process.
  `package.json` has been updated to reflect the presence of `package.js` and
  reference the latest versions of xstyle and put-selector, each of which now
  have a `package.js` of their own.

## Other Fixes

* Mouse events for expanding/collapsing rows in tree grids should be a bit more
  reliable. (#112)
* Rows expanded in a tree grid which has been started up but is currently hidden
  will now be rendered properly when re-shown. (#140)
* The `tree` and `editor` plugins can now both be used on the same column, by
  wrapping `editor` with `tree`. (#144)
* `sortable` now defaults to `false` for columns where `field` is `"_item"`
  or entirely unspecified (in which case there's nothing to sort by anyway).
  (#149)
* The `Pagination` extension now behaves appropriately with empty result sets.
  (#173)
* The `ColumnHider` extension now iterates over `subRows` rather than `columns`,
  making it a bit more reliable in general. (#164)
* A couple of issues with the `DijitRegistry` extension were identified and
  fixed. (#146, thanks jdohert)