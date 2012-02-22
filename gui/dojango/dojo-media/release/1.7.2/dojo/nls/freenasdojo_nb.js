require({cache:{
'dojox/form/nls/nb/CheckedMultiSelect':function(){
define(
"dojox/form/nls/nb/CheckedMultiSelect", ({
	invalidMessage: "Du må velge minst ett element.",
	multiSelectLabelText: "{num} element(er) valgt"
})
);

},
'dijit/nls/nb/common':function(){
define(
"dijit/nls/nb/common", //begin v1.x content
({
	buttonOk: "OK",
	buttonCancel: "Avbryt",
	buttonSave: "Lagre",
	itemClose: "Lukk"
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/nb/Filter':function(){
define(
"dojox/grid/enhanced/nls/nb/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "Tøm filter",
	"filterDefDialogTitle": "Filter",
	"ruleTitleTemplate": "Regel ${0}",
	
	"conditionEqual": "er lik",
	"conditionNotEqual": "er ikke lik",
	"conditionLess": "er mindre enn",
	"conditionLessEqual": "mindre enn eller lik",
	"conditionLarger": "er større enn",
	"conditionLargerEqual": "større enn eller lik",
	"conditionContains": "inneholder",
	"conditionIs": "er",
	"conditionStartsWith": "starter med",
	"conditionEndWith": "slutter med",
	"conditionNotContain": "inneholder ikke",
	"conditionIsNot": "er ikke",
	"conditionNotStartWith": "starter ikke med",
	"conditionNotEndWith": "slutter ikke med",
	"conditionBefore": "før",
	"conditionAfter": "etter",
	"conditionRange": "område",
	"conditionIsEmpty": "er tom",
	
	"all": "alle",
	"any": "minst en",
	"relationAll": "alle regler",
	"waiRelAll": "Samsvar med alle disse reglene:",
	"relationAny": "minst en regel",
	"waiRelAny": "Samsvar med minst en av disse reglene:",
	"relationMsgFront": "Samsvar med",
	"relationMsgTail": "",
	"and": "og",
	"or": "eller",
	
	"addRuleButton": "Legg til regel",
	"waiAddRuleButton": "Legg til en ny regel",
	"removeRuleButton": "Fjern regel",
	"waiRemoveRuleButtonTemplate": "Fjern regel ${0}",
	
	"cancelButton": "Avbryt",
	"waiCancelButton": "Avbryt denne dialogboksen",
	"clearButton": "Tøm",
	"waiClearButton": "Tøm filteret",
	"filterButton": "Filtrer",
	"waiFilterButton": "Send filteret",
	
	"columnSelectLabel": "Kolonne",
	"waiColumnSelectTemplate": "Kolonne for regel ${0}",
	"conditionSelectLabel": "Betingelse",
	"waiConditionSelectTemplate": "Betingelse for regel ${0}",
	"valueBoxLabel": "Verdi",
	"waiValueBoxTemplate": "Oppgi verdi som skal filtreres for regel ${0}",
	
	"rangeTo": "til",
	"rangeTemplate": "fra ${0} til ${1}",
	
	"statusTipHeaderColumn": "Kolonne",
	"statusTipHeaderCondition": "Regler",
	"statusTipTitle": "Filterlinje",
	"statusTipMsg": "Klikk på filterlinjen her for å filtrere på verdiene i ${0}.",
	"anycolumn": "enhver kolonne",
	"statusTipTitleNoFilter": "Filterlinje",
	"statusTipTitleHasFilter": "Filter",
	"statusTipRelAny": "Samsvar med minst en regel.",
	"statusTipRelAll": "Samsvar med alle regler.",
	
	"defaultItemsName": "elementer",
	"filterBarMsgHasFilterTemplate": "${0} av ${1} ${2} vist.",
	"filterBarMsgNoFilterTemplate": "Ikke brukt filter",
	
	"filterBarDefButton": "Definer filter",
	"waiFilterBarDefButton": "Filtrer tabellen",
	"a11yFilterBarDefButton": "Filtrer...",
	"filterBarClearButton": "Tøm filter",
	"waiFilterBarClearButton": "Tøm filteret",
	"closeFilterBarBtn": "Lukk filterlinjen",
	
	"clearFilterMsg": "Dette fjerner filteret og viser alle tilgjengelige poster.",
	"anyColumnOption": "Minst en kolonne",
	
	"trueLabel": "Sann",
	"falseLabel": "Usann"
})
//end v1.x content
);

},
'dojo/cldr/nls/nb/gregorian':function(){
define(
"dojo/cldr/nls/nb/gregorian", //begin v1.x content
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
	"field-weekday": "ukedag",
	"dateFormatItem-yyQQQQ": "QQQQ yy",
	"dateFormatItem-yQQQ": "QQQ y",
	"dateFormatItem-yMEd": "EEE d.M.yyyy",
	"dateFormatItem-MMMEd": "E d. MMM",
	"eraNarrow": [
		"f.Kr.",
		"e.Kr."
	],
	"dateFormat-long": "d. MMMM y",
	"months-format-wide": [
		"januar",
		"februar",
		"mars",
		"april",
		"mai",
		"juni",
		"juli",
		"august",
		"september",
		"oktober",
		"november",
		"desember"
	],
	"dateFormatItem-EEEd": "EEE d.",
	"dayPeriods-format-wide-pm": "PM",
	"dateFormat-full": "EEEE d. MMMM y",
	"dateFormatItem-Md": "d.M.",
	"field-era": "tidsalder",
	"dateFormatItem-yM": "M y",
	"months-standAlone-wide": [
		"januar",
		"februar",
		"mars",
		"april",
		"mai",
		"juni",
		"juli",
		"august",
		"september",
		"oktober",
		"november",
		"desember"
	],
	"timeFormat-short": "HH:mm",
	"quarters-format-wide": [
		"1. kvartal",
		"2. kvartal",
		"3. kvartal",
		"4. kvartal"
	],
	"timeFormat-long": "HH:mm:ss z",
	"field-year": "år",
	"dateFormatItem-yMMM": "MMM y",
	"dateFormatItem-yQ": "Q yyyy",
	"dateFormatItem-yyyyMMMM": "MMMM y",
	"field-hour": "time",
	"dateFormatItem-MMdd": "dd.MM",
	"months-format-abbr": [
		"jan.",
		"feb.",
		"mars",
		"apr.",
		"mai",
		"juni",
		"juli",
		"aug.",
		"sep.",
		"okt.",
		"nov.",
		"des."
	],
	"dateFormatItem-yyQ": "Q yy",
	"timeFormat-full": "'kl'. HH:mm:ss zzzz",
	"field-day-relative+0": "i dag",
	"field-day-relative+1": "i morgen",
	"field-day-relative+2": "i overmorgen",
	"field-day-relative+3": "i overovermorgen",
	"months-standAlone-abbr": [
		"jan.",
		"feb.",
		"mars",
		"apr.",
		"mai",
		"juni",
		"juli",
		"aug.",
		"sep.",
		"okt.",
		"nov.",
		"des."
	],
	"quarters-format-abbr": [
		"K1",
		"K2",
		"K3",
		"K4"
	],
	"quarters-standAlone-wide": [
		"1. kvartal",
		"2. kvartal",
		"3. kvartal",
		"4. kvartal"
	],
	"dateFormatItem-M": "L",
	"days-standAlone-wide": [
		"søndag",
		"mandag",
		"tirsdag",
		"onsdag",
		"torsdag",
		"fredag",
		"lørdag"
	],
	"dateFormatItem-yyMMM": "MMM yy",
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
	"field-minute": "minutt",
	"field-dayperiod": "AM/PM",
	"days-standAlone-abbr": [
		"søn.",
		"man.",
		"tir.",
		"ons.",
		"tor.",
		"fre.",
		"lør."
	],
	"dateFormatItem-d": "d.",
	"dateFormatItem-ms": "mm.ss",
	"field-day-relative+-1": "i går",
	"field-day-relative+-2": "i forgårs",
	"field-day-relative+-3": "i forforgårs",
	"dateFormatItem-MMMd": "d. MMM",
	"dateFormatItem-MEd": "E d.M",
	"field-day": "dag",
	"days-format-wide": [
		"søndag",
		"mandag",
		"tirsdag",
		"onsdag",
		"torsdag",
		"fredag",
		"lørdag"
	],
	"field-zone": "sone",
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
	"dateFormatItem-yyMM": "MM.yy",
	"dateFormatItem-hm": "h:mm a",
	"days-format-abbr": [
		"søn.",
		"man.",
		"tir.",
		"ons.",
		"tor.",
		"fre.",
		"lør."
	],
	"eraNames": [
		"f.Kr.",
		"e.Kr."
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
	"field-month": "måned",
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
	"dayPeriods-format-wide-am": "AM",
	"dateFormat-short": "dd.MM.yy",
	"field-second": "sekund",
	"dateFormatItem-yMMMEd": "EEE d. MMM y",
	"field-week": "uke",
	"dateFormat-medium": "d. MMM y",
	"dateFormatItem-Hms": "HH:mm:ss",
	"dateFormatItem-hms": "h:mm:ss a"
}
//end v1.x content
);
},
'dojo/cldr/nls/nb/number':function(){
define(
"dojo/cldr/nls/nb/number", //begin v1.x content
{
	"group": " ",
	"percentSign": "%",
	"exponential": "E",
	"scientificFormat": "#E0",
	"percentFormat": "#,##0 %",
	"list": ";",
	"infinity": "∞",
	"patternDigit": "#",
	"minusSign": "-",
	"decimal": ",",
	"nan": "NaN",
	"nativeZeroDigit": "0",
	"perMille": "‰",
	"decimalFormat": "#,##0.###",
	"currencyFormat": "¤ #,##0.00",
	"plusSign": "+"
}
//end v1.x content
);
},
'dojox/grid/enhanced/nls/nb/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/nb/EnhancedGrid", //begin v1.x content
({
	singleSort: "Enkeltsortering",
	nestedSort: "Nestet sortering",
	ascending: "Stigende",
	descending: "Synkende",
	sortingState: "${0} - ${1}",
	unsorted: "Ikke sorter denne kolonnen",
	indirectSelectionRadio: "Rad ${0}, enkeltvalg, valgknapp",
	indirectSelectionCheckBox: "Rad ${0}, flervalg, avmerkingsboks",
	selectAll: "Velg alle"
})
//end v1.x content
);


},
'dijit/_editor/nls/nb/commands':function(){
define(
"dijit/_editor/nls/nb/commands", //begin v1.x content
({
	'bold': 'Fet',
	'copy': 'Kopier',
	'cut': 'Klipp ut',
	'delete': 'Slett',
	'indent': 'Innrykk',
	'insertHorizontalRule': 'Vannrett strek',
	'insertOrderedList': 'Nummerert liste',
	'insertUnorderedList': 'Punktliste',
	'italic': 'Kursiv',
	'justifyCenter': 'Midtstill',
	'justifyFull': 'Juster',
	'justifyLeft': 'Venstrejuster',
	'justifyRight': 'Høyrejuster',
	'outdent': 'Fjern innrykk',
	'paste': 'Lim inn',
	'redo': 'Gjør om',
	'removeFormat': 'Fjern format',
	'selectAll': 'Velg alle',
	'strikethrough': 'Gjennomstreking',
	'subscript': 'Senket skrift',
	'superscript': 'Hevet skrift',
	'underline': 'Understreking',
	'undo': 'Angre',
	'unlink': 'Fjern kobling',
	'createLink': 'Opprett kobling',
	'toggleDir': 'Bytt retning',
	'insertImage': 'Sett inn bilde',
	'insertTable': 'Sett inn/rediger tabell',
	'toggleTableBorder': 'Bytt tabellkant',
	'deleteTable': 'Slett tabell',
	'tableProp': 'Tabellegenskap',
	'htmlToggle': 'HTML-kilde',
	'foreColor': 'Forgrunnsfarge',
	'hiliteColor': 'Bakgrunnsfarge',
	'plainFormatBlock': 'Avsnittsstil',
	'formatBlock': 'Avsnittsstil',
	'fontSize': 'Skriftstørrelse',
	'fontName': 'Skriftnavn',
	'tabIndent': 'Tabulatorinnrykk',
	"fullScreen": "Slå på/av full skjerm",
	"viewSource": "Vis HTML-kilde",
	"print": "Skriv ut",
	"newPage": "Ny side",
	/* Error messages */
	'systemShortcut': 'Handlingen "${0}" er bare tilgjengelig i nettleseren ved hjelp av en tastatursnarvei. Bruk ${1}.',
	'ctrlKey':'ctrl+${0}',
	'appleKey':'\u2318${0}' // "command" or open-apple key on Macintosh
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/nb/Pagination':function(){
define(
"dojox/grid/enhanced/nls/nb/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} av ${1} ${0}",
	"firstTip": "Første side",
	"lastTip": "Siste side",
	"nextTip": "Neste side",
	"prevTip": "Forrige side",
	"itemTitle": "elementer",
	"singularItemTitle": "element",
	"pageStepLabelTemplate": "Side ${0}",
	"pageSizeLabelTemplate": "${0} elementer per side",
	"allItemsLabelTemplate": "Alle elementer",
	"gotoButtonTitle": "Gå til en bestemt side",
	"dialogTitle": "Gå til side",
	"dialogIndication": "Oppgi sidetallet",
	"pageCountIndication": " (${0} sider)",
	"dialogConfirm": "Utfør",
	"dialogCancel": "Avbryt",
	"all": "alle"
})
//end v1.x content
);

},
'dijit/form/nls/nb/validate':function(){
define(
"dijit/form/nls/nb/validate", //begin v1.x content
({
	invalidMessage: "Den angitte verdien er ikke gyldig.",
	missingMessage: "Denne verdien er obligatorisk.",
	rangeMessage: "Denne verdien er utenfor gyldig område."
})
//end v1.x content
);

},
'dojo/cldr/nls/nb/currency':function(){
define(
"dojo/cldr/nls/nb/currency", //begin v1.x content
{
	"HKD_displayName": "Hongkong-dollar",
	"CHF_displayName": "sveitsiske franc",
	"CHF_symbol": "CHF",
	"JPY_symbol": "JPY",
	"CAD_displayName": "kanadiske dollar",
	"CNY_displayName": "kinesiske yuan renminbi",
	"USD_symbol": "USD",
	"AUD_displayName": "australske dollar",
	"JPY_displayName": "japanske yen",
	"CAD_symbol": "CAD",
	"USD_displayName": "amerikanske dollar",
	"EUR_symbol": "EUR",
	"CNY_symbol": "CNY",
	"GBP_displayName": "britiske pund sterling",
	"GBP_symbol": "GBP",
	"AUD_symbol": "AUD",
	"EUR_displayName": "euro"
}
//end v1.x content
);
},
'dijit/form/nls/nb/ComboBox':function(){
define(
"dijit/form/nls/nb/ComboBox", //begin v1.x content
({
		previousMessage: "Tidligere valg",
		nextMessage: "Flere valg"
})
//end v1.x content
);

},
'dijit/nls/nb/loading':function(){
define(
"dijit/nls/nb/loading", //begin v1.x content
({
	loadingState: "Laster inn...",
	errorState: "Det oppsto en feil"
})
//end v1.x content
);

}}});
define("dojo/nls/freenasdojo_nb", [], 1);
