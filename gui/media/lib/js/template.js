/* template.js, Copyright (C) 2007 - 2010 YOOtheme GmbH */

var YOOTemplate = {
		
	start: function() {

		/* Match height of div tags */
		YOOTemplate.matchHeights();

		/* Accordion menu */
		new YOOAccordionMenu('div#middle ul.menu li.toggler', 'ul.accordion', { accordion: 'slide' });

		/* Dropdown menu */
		var dropdown = new YOODropdownMenu('menu', { mode: 'height', dropdownSelector: 'div.dropdown', transition: Fx.Transitions.Expo.easeOut });
		dropdown.matchHeight();

		/* Fancy menu */
		new YOOFancyMenu('menu', { mode: 'fade', transition: Fx.Transitions.expoOut, duration: 500 });

		/* set hover color */
		var hoverColor;
		switch (YtSettings.color) {
			case 'lilac':
				hoverColorMenu = '#4B2C54';
				leaveColorMenu = '#5D4661';
				hoverColorSubMenu = '#866D8D';
				leaveColorSubMenu = '#684971';
				break;
			case 'gaming':
				hoverColorMenu = '#272727';
				leaveColorMenu = '#464646';
				hoverColorSubMenu = '#54748D';
				leaveColorSubMenu = '#295171';
				break;
			case 'cooking':
				hoverColorMenu = '#49413D';
				leaveColorMenu = '#584F4A';
				hoverColorSubMenu = '#7DB5BB';
				leaveColorSubMenu = '#5CA2AA';
				break;
			case 'landscape':
				hoverColorMenu = '#2E4355';
				leaveColorMenu = '#496281';
				hoverColorSubMenu = '#9EC059';
				leaveColorSubMenu = '#86B030';
				break;
			case 'orange':
				hoverColorMenu = '#422C23';
				leaveColorMenu = '#543E37';
				hoverColorSubMenu = '#C9923B';
				leaveColorSubMenu = '#BC770A';
				break;
			case 'black':
				hoverColorMenu = '#1F2020';
				leaveColorMenu = '#2F3131';
				hoverColorSubMenu = '#794D55';
				leaveColorSubMenu = '#57212A';
				break;
			case 'brown':
				hoverColorMenu = '#34342D';
				leaveColorMenu = '#49473D';
				hoverColorSubMenu = '#7D796F';
				leaveColorSubMenu = '#5D584B';
				break;
			case 'blue':
				hoverColorMenu = '#233B50';
				leaveColorMenu = '#384E63';
				hoverColorSubMenu = '#f6f6f6';
				leaveColorSubMenu = '#c6c6c6';
				break;
			case 'beige':
				hoverColorMenu = '#5B564C';
				leaveColorMenu = '#6E6C65';
				hoverColorSubMenu = '#A1A19D';
				leaveColorSubMenu = '#898984';
				break;
			case 'green':
				hoverColorMenu = '#4E643F';
				leaveColorMenu = '#6B7E5B';
				hoverColorSubMenu = '#A2B18D';
				leaveColorSubMenu = '#8B9E70';
				break;
			case 'red':
				hoverColorMenu = '#502123';
				leaveColorMenu = '#663235';
				hoverColorSubMenu = '#A56669';
				leaveColorSubMenu = '#8F4043';
				break;
			default:
				hoverColorMenu = '#393C45';
				leaveColorMenu = '#4C535A';
				hoverColorSubMenu = '#7A8086';
				leaveColorSubMenu = '#596068';
		}

		/* Morph: main menu - level2 (color) */
		var menuEnter = { 'background-color': hoverColorMenu};
		var menuLeave = { 'background-color': leaveColorMenu};

		new YOOMorph('div#menu .hover-box1', menuEnter, menuLeave,
			{ transition: Fx.Transitions.linear, duration: 0, ignore: 'div#menu li li.separator .hover-box1, div#menu .mod-dropdown .hover-box1' },
			{ transition: Fx.Transitions.sineIn, duration: 500 });

		/* Morph: mod-rider sub menu - level1 */
		var submenuEnter = { 'background-color': hoverColorSubMenu };
		var submenuLeave = { 'background-color': leaveColorSubMenu };

		new YOOMorph('div.mod-rider ul.menu a.level1, div.mod-rider ul.menu span.level1', submenuEnter, submenuLeave,
			{ transition: Fx.Transitions.expoOut, duration: 0 },
			{ transition: Fx.Transitions.sineIn, duration: 300 });

		/* Morph: mod-line sub menu - level1 */
		var submenuEnter = { 'color': '#000000', 'padding-left': 5};
		var submenuLeave = { 'color': '#646464', 'padding-left': 0};

		new YOOMorph('div.mod-band ul.menu span.bg', submenuEnter, submenuLeave,
			{ transition: Fx.Transitions.expoOut, duration: 100 },
			{ transition: Fx.Transitions.sineIn, duration: 300 });

		/* Smoothscroll */
		new SmoothScroll({ duration: 500, transition: Fx.Transitions.Expo.easeOut });
	},

	/* Match height of div tags */
	matchHeights: function() {
		YOOBase.matchHeight('div.headerbox div.deepest', 20);
		YOOBase.matchHeight('div.topbox div.deepest', 20);
		YOOBase.matchHeight('div.bottombox div.deepest', 20);
		YOOBase.matchHeight('div.maintopbox div.deepest', 20);
		YOOBase.matchHeight('div.mainbottombox div.deepest', 20);
		YOOBase.matchHeight('div.contenttopbox div.deepest', 20);
		YOOBase.matchHeight('div.contentbottombox div.deepest', 20);
		YOOBase.matchHeight('div.main-wrapper-1, #left, #right', 20);
	}

};

/* Add functions on window load */
window.addEvent('domready', YOOTemplate.start);
