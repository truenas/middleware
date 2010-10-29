/* ie6fix.js, Copyright (C) 2007 - 2010 YOOtheme GmbH */

function loadIE6Fix() {

	correctPngBackground('.correct-png', 'crop');
	
	// layout
	fixPngBackground('div.main-wrapper-t1, div.main-wrapper-t2, div.main-wrapper-b1, div.main-wrapper-b2');
	fixPngBackground('#breadcrumbs, #breadcrumbs .box-1, #breadcrumbs .box-2, #breadcrumbs .box-3');
	
	// typography & joomla
	fixPngBackground('div.info, div.alert, div.download, div.tip, span.info, span.alert, span.download, span.tip');
	fixPngBackground('ul.arrow li, ul.checkbox li, ul.check li, ul.star li');
	fixPngBackground('blockquote.quotation, blockquote.quotation p');
	fixPngBackground('ol.disc');
	fixPngBackground('a.readmore, a.readon');
	fixPngBackground('.default-search div.searchbox');

	// menu
	fixPngBackground('#date, #toolbar .menu li a, #footer .menu li a');
	fixPngBackground('#menu .dropdown-t1, #menu .dropdown-t2, #menu .dropdown-t3, #menu .dropdown-1, #menu .dropdown-2, #menu .dropdown-b1, #menu .dropdown-b2, #menu .dropdown-b3');
	fixPngBackground('#menu li.active .level1, #menu li.active .level1 span.bg, div#menu div.fancy div.fancy-1, div#menu div.fancy div.fancy-2');
	fixPngBackground('#menu span.icon');
	fixPngBackground('div.mod-rider ul.menu a.level1, div.mod-rider ul.menu span.level1');
	
	// module
	fixPngBackground('div.module div.badge');
	fixPngBackground('div.module h3.header span.icon');
	fixPngBackground('div.mod-rider div.box-t1, div.mod-rider div.box-t2, div.mod-rider div.box-1, div.mod-rider div.box-b1, div.mod-rider div.box-b2, div.mod-rider h3.header');
	fixPngBackground('div.mod-rounded div.box-t1, div.mod-rounded div.box-t2, div.mod-rounded div.box-t3, div.mod-rounded div.box-1, div.mod-rounded div.box-2, div.mod-rounded div.box-b1, div.mod-rounded div.box-b2, div.mod-rounded div.box-b3, div.mod-rounded h3.header, div.mod-rounded span.header-2, div.mod-rounded span.header-3');
	fixPngBackground('div.mod-header h3.header, div.mod-header span.header-2, div.mod-header span.header-3');
	fixPngBackground('div.mod-polaroid div.box-b1, div.mod-polaroid div.box-b2, div.mod-polaroid div.box-b3, div.mod-polaroid div.badge-tape');
	fixPngBackground('div.mod-postit div.box-b1, div.mod-postit div.box-b2, div.mod-postit div.box-b3');
	fixPngBackground('div.mod-tab h3.header, div.mod-tab span.header-2');

	/* extensions */
	fixPngBackground('#top div.blank-h div.yoo-scroller div.scrollarea, #top div.blank-h div.yoo-scroller div.scrollarea-l');
	fixPngBackground('div.slideshow div.yoo-carousel .prev a, div.slideshow div.yoo-carousel .next a');

	DD_belatedPNG.fix('.png_bg');
	
	// menu
	addHover('#menu li.level1, #menu .hover-box1');
	
	// search
	addHover('.default-search div.searchbox');
	addHover('div.mod-line ul.menu span.level1');
	addFocus('.default-search div.searchbox input');
	
}

/* Add functions on window load */
window.addEvent('domready', loadIE6Fix);
window.addEvent('load', correctPngInline);

/* Fix PNG background */
function fixPngBackground(selector) {
	$ES(selector).each(function(element){
		element.addClass('png_bg');
	});
}