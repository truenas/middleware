require({cache:{
'dojox/form/nls/sv/CheckedMultiSelect':function(){
define(
"dojox/form/nls/sv/CheckedMultiSelect", ({
	invalidMessage: "Du måste välja minst ett objekt.",
	multiSelectLabelText: "{num} objekt har valts"
})
);

},
'dijit/nls/sv/common':function(){
define(
"dijit/nls/sv/common", //begin v1.x content
({
	buttonOk: "OK",
	buttonCancel: "Avbryt",
	buttonSave: "Spara",
	itemClose: "Stäng"
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/sv/Filter':function(){
define(
"dojox/grid/enhanced/nls/sv/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "Rensa filter",
	"filterDefDialogTitle": "Filter",
	"ruleTitleTemplate": "Regel ${0}",
	
	"conditionEqual": "lika med",
	"conditionNotEqual": "inte lika med",
	"conditionLess": "är mindre än",
	"conditionLessEqual": "mindre eller lika med",
	"conditionLarger": "är större än",
	"conditionLargerEqual": "större än eller lika med",
	"conditionContains": "innehåller",
	"conditionIs": "är",
	"conditionStartsWith": "börjar med",
	"conditionEndWith": "slutar med",
	"conditionNotContain": "innehåller inte",
	"conditionIsNot": "är inte",
	"conditionNotStartWith": "börjar inte med",
	"conditionNotEndWith": "slutar inte med",
	"conditionBefore": "före",
	"conditionAfter": "efter",
	"conditionRange": "intervall",
	"conditionIsEmpty": "är tom",
	
	"all": "alla",
	"any": "någon",
	"relationAll": "alla regler",
	"waiRelAll": "Matcha alla följande regler:",
	"relationAny": "någon regel",
	"waiRelAny": "Matcha någon av följande regler:",
	"relationMsgFront": "Matcha",
	"relationMsgTail": "",
	"and": "och",
	"or": "eller",
	
	"addRuleButton": "Lägg till regel",
	"waiAddRuleButton": "Lägg till en ny regel",
	"removeRuleButton": "Ta bort regel",
	"waiRemoveRuleButtonTemplate": "Ta bort regel ${0}",
	
	"cancelButton": "Avbryt",
	"waiCancelButton": "Avbryt dialogen",
	"clearButton": "Rensa",
	"waiClearButton": "Rensa filtret",
	"filterButton": "Filtrera",
	"waiFilterButton": "Filtrera",
	
	"columnSelectLabel": "Kolumn",
	"waiColumnSelectTemplate": "Kolumn för regel ${0}",
	"conditionSelectLabel": "Villkor",
	"waiConditionSelectTemplate": "Villkor för regel ${0}",
	"valueBoxLabel": "Värde",
	"waiValueBoxTemplate": "Ange värde för filtrering efter regeln ${0}",
	
	"rangeTo": "till",
	"rangeTemplate": "från ${0} till ${1}",
	
	"statusTipHeaderColumn": "Kolumn",
	"statusTipHeaderCondition": "Regler",
	"statusTipTitle": "Filterfält",
	"statusTipMsg": "Klicka på filterfältet om du vill filtrera värden i ${0}.",
	"anycolumn": "alla kolumner",
	"statusTipTitleNoFilter": "Filterfält",
	"statusTipTitleHasFilter": "Filter",
	"statusTipRelAny": "Matcha någon regel.",
	"statusTipRelAll": "Matcha alla regler.",
	
	"defaultItemsName": "objekt",
	"filterBarMsgHasFilterTemplate": "${0} av ${1} ${2} visas.",
	"filterBarMsgNoFilterTemplate": "Inget filter tillämpat",
	
	"filterBarDefButton": "Definiera filter",
	"waiFilterBarDefButton": "Filtrera tabellen",
	"a11yFilterBarDefButton": "Filter...",
	"filterBarClearButton": "Rensa filter",
	"waiFilterBarClearButton": "Rensa filtret",
	"closeFilterBarBtn": "Stäng filterfält",
	
	"clearFilterMsg": "Tar bort filtret och visar alla tillgängliga poster.",
	"anyColumnOption": "Alla kolumner",
	
	"trueLabel": "Sant",
	"falseLabel": "Falskt"
})
//end v1.x content
);

},
'dojo/cldr/nls/sv/gregorian':function(){
define(
"dojo/cldr/nls/sv/gregorian", //begin v1.x content
{
	"months-format-narrow": [
		"J",
		"F",
		"M",
		"A",
		"M",
		"J",
		"J",
		"A",
		"S",
		"O",
		"N",
		"D"
	],
	"quarters-standAlone-narrow": [
		"1",
		"2",
		"3",
		"4"
	],
	"field-weekday": "veckodag",
	"dateFormatItem-yQQQ": "y QQQ",
	"dateFormatItem-yMEd": "EEE, yyyy-MM-dd",
	"dateFormatItem-MMMEd": "E d MMM",
	"eraNarrow": [
		"f.Kr.",
		"e.Kr."
	],
	"dateFormat-long": "d MMMM y",
	"months-format-wide": [
		"januari",
		"februari",
		"mars",
		"april",
		"maj",
		"juni",
		"juli",
		"augusti",
		"september",
		"oktober",
		"november",
		"december"
	],
	"dateFormatItem-EEEd": "EEE d",
	"dayPeriods-format-wide-pm": "em",
	"dateFormat-full": "EEEE'en' 'den' d:'e' MMMM y",
	"dateFormatItem-Md": "d/M",
	"dateFormatItem-MMMMEEEd": "EEE d MMMM",
	"field-era": "era",
	"dateFormatItem-yM": "yyyy-MM",
	"months-standAlone-wide": [
		"januari",
		"februari",
		"mars",
		"april",
		"maj",
		"juni",
		"juli",
		"augusti",
		"september",
		"oktober",
		"november",
		"december"
	],
	"timeFormat-short": "HH:mm",
	"quarters-format-wide": [
		"1:a kvartalet",
		"2:a kvartalet",
		"3:e kvartalet",
		"4:e kvartalet"
	],
	"timeFormat-long": "HH:mm:ss z",
	"field-year": "år",
	"dateFormatItem-yMMM": "MMM y",
	"dateFormatItem-yQ": "yyyy Q",
	"field-hour": "timme",
	"dateFormatItem-MMdd": "dd/MM",
	"months-format-abbr": [
		"jan",
		"feb",
		"mar",
		"apr",
		"maj",
		"jun",
		"jul",
		"aug",
		"sep",
		"okt",
		"nov",
		"dec"
	],
	"dateFormatItem-yyQ": "Q yy",
	"timeFormat-full": "'kl'. HH:mm:ss zzzz",
	"field-day-relative+0": "i dag",
	"field-day-relative+1": "i morgon",
	"field-day-relative+2": "i övermorgon",
	"field-day-relative+3": "i överövermorgon",
	"months-standAlone-abbr": [
		"jan",
		"feb",
		"mar",
		"apr",
		"maj",
		"jun",
		"jul",
		"aug",
		"sep",
		"okt",
		"nov",
		"dec"
	],
	"quarters-format-abbr": [
		"K1",
		"K2",
		"K3",
		"K4"
	],
	"quarters-standAlone-wide": [
		"1:a kvartalet",
		"2:a kvartalet",
		"3:e kvartalet",
		"4:e kvartalet"
	],
	"dateFormatItem-M": "L",
	"days-standAlone-wide": [
		"söndag",
		"måndag",
		"tisdag",
		"onsdag",
		"torsdag",
		"fredag",
		"lördag"
	],
	"dateFormatItem-yyyyMMM": "MMM y",
	"dateFormatItem-MMMMd": "d:'e' MMMM",
	"dateFormatItem-yyMMM": "MMM -yy",
	"timeFormat-medium": "HH:mm:ss",
	"dateFormatItem-Hm": "HH:mm",
	"quarters-standAlone-abbr": [
		"K1",
		"K2",
		"K3",
		"K4"
	],
	"eraAbbr": [
		"f.Kr.",
		"e.Kr."
	],
	"field-minute": "minut",
	"field-dayperiod": "fm/em",
	"days-standAlone-abbr": [
		"sön",
		"mån",
		"tis",
		"ons",
		"tors",
		"fre",
		"lör"
	],
	"dateFormatItem-d": "d",
	"dateFormatItem-ms": "mm:ss",
	"field-day-relative+-1": "i går",
	"field-day-relative+-2": "i förrgår",
	"field-day-relative+-3": "i förrförrgår",
	"dateFormatItem-MMMd": "d MMM",
	"dateFormatItem-MEd": "E d/M",
	"field-day": "dag",
	"days-format-wide": [
		"söndag",
		"måndag",
		"tisdag",
		"onsdag",
		"torsdag",
		"fredag",
		"lördag"
	],
	"field-zone": "tidszon",
	"dateFormatItem-yyyyMM": "yyyy-MM",
	"dateFormatItem-y": "y",
	"months-standAlone-narrow": [
		"J",
		"F",
		"M",
		"A",
		"M",
		"J",
		"J",
		"A",
		"S",
		"O",
		"N",
		"D"
	],
	"dateFormatItem-yyMM": "yy-MM",
	"dateFormatItem-hm": "h:mm a",
	"days-format-abbr": [
		"sön",
		"mån",
		"tis",
		"ons",
		"tors",
		"fre",
		"lör"
	],
	"eraNames": [
		"före Kristus",
		"efter Kristus"
	],
	"days-format-narrow": [
		"S",
		"M",
		"T",
		"O",
		"T",
		"F",
		"L"
	],
	"field-month": "månad",
	"days-standAlone-narrow": [
		"S",
		"M",
		"T",
		"O",
		"T",
		"F",
		"L"
	],
	"dateFormatItem-MMM": "LLL",
	"dayPeriods-format-wide-am": "fm",
	"dateFormatItem-MMMMEd": "E d:'e' MMMM",
	"dateFormat-short": "yyyy-MM-dd",
	"dateFormatItem-MMd": "d/M",
	"field-second": "sekund",
	"dateFormatItem-yMMMEd": "EEE d MMM y",
	"field-week": "vecka",
	"dateFormat-medium": "d MMM y",
	"dateFormatItem-yyyyQQQQ": "QQQQ y",
	"dateFormatItem-Hms": "HH:mm:ss",
	"dateFormatItem-hms": "h:mm:ss a"
}
//end v1.x content
);
},
'dojo/cldr/nls/sv/number':function(){
define(
"dojo/cldr/nls/sv/number", //begin v1.x content
{
	"group": " ",
	"percentSign": "%",
	"exponential": "×10^",
	"scientificFormat": "#E0",
	"percentFormat": "#,##0 %",
	"list": ";",
	"infinity": "∞",
	"patternDigit": "#",
	"minusSign": "−",
	"decimal": ",",
	"nan": "¤¤¤",
	"nativeZeroDigit": "0",
	"perMille": "‰",
	"decimalFormat": "#,##0.###",
	"currencyFormat": "#,##0.00 ¤",
	"plusSign": "+"
}
//end v1.x content
);
},
'dojox/grid/enhanced/nls/sv/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/sv/EnhancedGrid", //begin v1.x content
({
	singleSort: "Enkel sortering",
	nestedSort: "Nästlad sortering",
	ascending: "Stigande",
	descending: "Fallande",
	sortingState: "${0} - ${1}",
	unsorted: "Sortera inte den här kolumnen",
	indirectSelectionRadio: "Rad ${0}, ett enda val, alternativruta",
	indirectSelectionCheckBox: "Rad ${0}, flera val, kryssruta",
	selectAll: "Markera alla "
})
//end v1.x content
);


},
'dijit/_editor/nls/sv/commands':function(){
define(
"dijit/_editor/nls/sv/commands", //begin v1.x content
({
	'bold': 'Fetstil',
	'copy': 'Kopiera',
	'cut': 'Klipp ut',
	'delete': 'Ta bort',
	'indent': 'Indrag',
	'insertHorizontalRule': 'Horisontell linjal',
	'insertOrderedList': 'Numrerad lista',
	'insertUnorderedList': 'Punktlista',
	'italic': 'Kursiv',
	'justifyCenter': 'Centrera',
	'justifyFull': 'Marginaljustera',
	'justifyLeft': 'Vänsterjustera',
	'justifyRight': 'Högerjustera',
	'outdent': 'Utdrag',
	'paste': 'Klistra in',
	'redo': 'Gör om',
	'removeFormat': 'Ta bort format',
	'selectAll': 'Markera allt',
	'strikethrough': 'Genomstruken',
	'subscript': 'Nedsänkt',
	'superscript': 'Upphöjt',
	'underline': 'Understrykning',
	'undo': 'Ångra',
	'unlink': 'Ta bort länk',
	'createLink': 'Skapa länk',
	'toggleDir': 'Växla riktning',
	'insertImage': 'Infoga bild',
	'insertTable': 'Infoga/redigera tabell',
	'toggleTableBorder': 'Aktivera/avaktivera tabellram',
	'deleteTable': 'Ta bort tabell',
	'tableProp': 'Tabellegenskap',
	'htmlToggle': 'HTML-källkod',
	'foreColor': 'Förgrundsfärg',
	'hiliteColor': 'Bakgrundsfärg',
	'plainFormatBlock': 'Styckeformat',
	'formatBlock': 'Styckeformat',
	'fontSize': 'Teckenstorlek',
	'fontName': 'Teckensnittsnamn',
	'tabIndent': 'Tabbindrag',
	"fullScreen": "Växla helskärm",
	"viewSource": "Visa HTML-kod",
	"print": "Skriv ut",
	"newPage": "Ny sida",
	/* Error messages */
	'systemShortcut': 'Åtgärden "${0}" är endast tillgänglig i webbläsaren med hjälp av ett kortkommando. Använd ${1}.',
	'ctrlKey':'Ctrl+${0}',
	'appleKey':'\u2318+${0}' // "command" or open-apple key on Macintosh
})

//end v1.x content
);

},
'dojox/grid/enhanced/nls/sv/Pagination':function(){
define(
"dojox/grid/enhanced/nls/sv/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} av ${1} ${0}",
	"firstTip": "Första sidan",
	"lastTip": "Sista sidan",
	"nextTip": "Nästa sida",
	"prevTip": "Föregående sida",
	"itemTitle": "objekt",
	"singularItemTitle": "objekt",
	"pageStepLabelTemplate": "Sida ${0}",
	"pageSizeLabelTemplate": "${0} objekt per sida",
	"allItemsLabelTemplate": "Alla objekt",
	"gotoButtonTitle": "Gå till en viss sida",
	"dialogTitle": "Gå till sidan",
	"dialogIndication": "Ange sidnummer",
	"pageCountIndication": " (${0} sidor)",
	"dialogConfirm": "Gå",
	"dialogCancel": "Avbryt",
	"all": "alla"
})
//end v1.x content
);

},
'dijit/form/nls/sv/validate':function(){
define(
"dijit/form/nls/sv/validate", //begin v1.x content
({
	invalidMessage: "Det angivna värdet är ogiltigt.",
	missingMessage: "Värdet är obligatoriskt.",
	rangeMessage: "Värdet är utanför intervallet."
})
//end v1.x content
);

},
'dojo/cldr/nls/sv/currency':function(){
define(
"dojo/cldr/nls/sv/currency", //begin v1.x content
{
	"HKD_displayName": "Hongkong-dollar",
	"CHF_displayName": "schweizisk franc",
	"CHF_symbol": "CHF",
	"CAD_displayName": "kanadensisk dollar",
	"CNY_displayName": "kinesisk yuan renminbi",
	"AUD_displayName": "australisk dollar",
	"JPY_displayName": "japansk yen",
	"CAD_symbol": "CAD",
	"USD_displayName": "US-dollar",
	"CNY_symbol": "CNY",
	"GBP_displayName": "brittiskt pund sterling",
	"EUR_displayName": "euro"
}
//end v1.x content
);
},
'dijit/form/nls/sv/ComboBox':function(){
define(
"dijit/form/nls/sv/ComboBox", //begin v1.x content
({
		previousMessage: "Föregående alternativ",
		nextMessage: "Fler alternativ"
})
//end v1.x content
);

},
'dijit/nls/sv/loading':function(){
define(
"dijit/nls/sv/loading", //begin v1.x content
({
	loadingState: "Läser in...",
	errorState: "Det uppstod ett fel."
})
//end v1.x content
);

}}});
define("dojo/nls/freenasdojo_sv", [], 1);
