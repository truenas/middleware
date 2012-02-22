require({cache:{
'dojox/form/nls/nl/CheckedMultiSelect':function(){
define(
"dojox/form/nls/nl/CheckedMultiSelect", ({
	invalidMessage: "Er moet te minste één item worden geselecteerd.",
	multiSelectLabelText: "{num} item(s) geselecteerd"
})
);

},
'dojox/form/nls/nl-nl/CheckedMultiSelect':function(){
define('dojox/form/nls/nl-nl/CheckedMultiSelect',{});
},
'dijit/nls/nl/common':function(){
define(
"dijit/nls/nl/common", //begin v1.x content
({
	buttonOk: "OK",
	buttonCancel: "Annuleren",
	buttonSave: "Opslaan",
	itemClose: "Sluiten"
})
//end v1.x content
);

},
'dijit/nls/nl-nl/common':function(){
define('dijit/nls/nl-nl/common',{});
},
'dojox/grid/enhanced/nls/nl/Filter':function(){
define(
"dojox/grid/enhanced/nls/nl/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "Filter wissen",
	"filterDefDialogTitle": "Filteren",
	"ruleTitleTemplate": "Regel ${0}",
	
	"conditionEqual": "gelijk aan",
	"conditionNotEqual": "niet gelijk aan",
	"conditionLess": "is kleiner dan",
	"conditionLessEqual": "kleiner dan of gelijk aan",
	"conditionLarger": "is groter dan",
	"conditionLargerEqual": "groter dan of gelijk aan",
	"conditionContains": "bevat",
	"conditionIs": "is",
	"conditionStartsWith": "begint met",
	"conditionEndWith": "eindigt op",
	"conditionNotContain": "bevat niet",
	"conditionIsNot": "is niet",
	"conditionNotStartWith": "begint niet met",
	"conditionNotEndWith": "eindigt niet op",
	"conditionBefore": "voor",
	"conditionAfter": "na",
	"conditionRange": "bereik",
	"conditionIsEmpty": "is leeg",
	
	"all": "alle",
	"any": "een of meer",
	"relationAll": "alle regels",
	"waiRelAll": "Voldoen aan al deze regels:",
	"relationAny": "een of meer regels",
	"waiRelAny": "Voldoen aan een van deze regels:",
	"relationMsgFront": "Voldoen aan",
	"relationMsgTail": "",
	"and": "en",
	"or": "of",
	
	"addRuleButton": "Regel toevoegen",
	"waiAddRuleButton": "Een nieuwe regel toevoegen",
	"removeRuleButton": "Regel verwijderen",
	"waiRemoveRuleButtonTemplate": "Regel ${0} verwijderen",
	
	"cancelButton": "Annuleren",
	"waiCancelButton": "Dit dialoogvenster annuleren",
	"clearButton": "Leegmaken",
	"waiClearButton": "Het filter wissen",
	"filterButton": "Filteren",
	"waiFilterButton": "Het filter verzenden",
	
	"columnSelectLabel": "Kolom",
	"waiColumnSelectTemplate": "Kolom voor regel ${0}",
	"conditionSelectLabel": "Voorwaarde",
	"waiConditionSelectTemplate": "Voorwaarde voor regel ${0}",
	"valueBoxLabel": "Waarde",
	"waiValueBoxTemplate": "Geef een filterwaarde op voor regel ${0}",
	
	"rangeTo": "tot",
	"rangeTemplate": "van ${0} tot ${1}",
	
	"statusTipHeaderColumn": "Kolom",
	"statusTipHeaderCondition": "Regels",
	"statusTipTitle": "Filterbalk",
	"statusTipMsg": "Klik hier op de filterbalk om te filteren op waarden in ${0}.",
	"anycolumn": "een kolom",
	"statusTipTitleNoFilter": "Filterbalk",
	"statusTipTitleHasFilter": "Filter",
	"statusTipRelAny": "Voldoen aan een van de regels.",
	"statusTipRelAll": "Voldoen aan alle regels.",
	
	"defaultItemsName": "items",
	"filterBarMsgHasFilterTemplate": "${0} van ${1} ${2} afgebeeld.",
	"filterBarMsgNoFilterTemplate": "Geen filter toegepast",
	
	"filterBarDefButton": "Filter definiëren",
	"waiFilterBarDefButton": "De tabel filteren",
	"a11yFilterBarDefButton": "Filteren...",
	"filterBarClearButton": "Filter wissen",
	"waiFilterBarClearButton": "Het filter wissen",
	"closeFilterBarBtn": "Filterbalk sluiten",
	
	"clearFilterMsg": "Hiermee verwijdert u het filter en worden alle beschikbare records afgebeeld.",
	"anyColumnOption": "Een kolom",
	
	"trueLabel": "Waar",
	"falseLabel": "Onwaar"
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/nl-nl/Filter':function(){
define('dojox/grid/enhanced/nls/nl-nl/Filter',{});
},
'dojo/cldr/nls/nl/gregorian':function(){
define(
"dojo/cldr/nls/nl/gregorian", //begin v1.x content
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
	"field-weekday": "Dag van de week",
	"dateFormatItem-yyQQQQ": "QQQQ yy",
	"dateFormatItem-yQQQ": "QQQ y",
	"dateFormatItem-yMEd": "EEE d-M-y",
	"dateFormatItem-MMMEd": "E d MMM",
	"eraNarrow": [
		"v. Chr.",
		"n. Chr."
	],
	"dateFormat-long": "d MMMM y",
	"months-format-wide": [
		"januari",
		"februari",
		"maart",
		"april",
		"mei",
		"juni",
		"juli",
		"augustus",
		"september",
		"oktober",
		"november",
		"december"
	],
	"dayPeriods-format-wide-pm": "PM",
	"dateFormat-full": "EEEE d MMMM y",
	"dateFormatItem-Md": "d-M",
	"field-era": "Tijdperk",
	"dateFormatItem-yM": "M-y",
	"months-standAlone-wide": [
		"januari",
		"februari",
		"maart",
		"april",
		"mei",
		"juni",
		"juli",
		"augustus",
		"september",
		"oktober",
		"november",
		"december"
	],
	"timeFormat-short": "HH:mm",
	"quarters-format-wide": [
		"1e kwartaal",
		"2e kwartaal",
		"3e kwartaal",
		"4e kwartaal"
	],
	"timeFormat-long": "HH:mm:ss z",
	"field-year": "Jaar",
	"dateFormatItem-yMMM": "MMM y",
	"dateFormatItem-yQ": "Q yyyy",
	"dateFormatItem-yyyyMMMM": "MMMM y",
	"field-hour": "Uur",
	"dateFormatItem-MMdd": "dd-MM",
	"months-format-abbr": [
		"jan.",
		"feb.",
		"mrt.",
		"apr.",
		"mei",
		"jun.",
		"jul.",
		"aug.",
		"sep.",
		"okt.",
		"nov.",
		"dec."
	],
	"dateFormatItem-yyQ": "Q yy",
	"timeFormat-full": "HH:mm:ss zzzz",
	"field-day-relative+0": "vandaag",
	"field-day-relative+1": "morgen",
	"field-day-relative+2": "overmorgen",
	"field-day-relative+3": "overovermorgen",
	"months-standAlone-abbr": [
		"jan.",
		"feb.",
		"mrt.",
		"apr.",
		"mei",
		"jun.",
		"jul.",
		"aug.",
		"sep.",
		"okt.",
		"nov.",
		"dec."
	],
	"quarters-format-abbr": [
		"K1",
		"K2",
		"K3",
		"K4"
	],
	"quarters-standAlone-wide": [
		"1e kwartaal",
		"2e kwartaal",
		"3e kwartaal",
		"4e kwartaal"
	],
	"dateFormatItem-M": "L",
	"days-standAlone-wide": [
		"zondag",
		"maandag",
		"dinsdag",
		"woensdag",
		"donderdag",
		"vrijdag",
		"zaterdag"
	],
	"dateFormatItem-MMMMd": "d MMMM",
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
		"v. Chr.",
		"n. Chr."
	],
	"field-minute": "Minuut",
	"field-dayperiod": "AM/PM",
	"days-standAlone-abbr": [
		"zo",
		"ma",
		"di",
		"wo",
		"do",
		"vr",
		"za"
	],
	"dateFormatItem-d": "d",
	"dateFormatItem-ms": "mm:ss",
	"field-day-relative+-1": "gisteren",
	"field-day-relative+-2": "eergisteren",
	"field-day-relative+-3": "eereergisteren",
	"dateFormatItem-MMMd": "d-MMM",
	"dateFormatItem-MEd": "E d-M",
	"field-day": "Dag",
	"days-format-wide": [
		"zondag",
		"maandag",
		"dinsdag",
		"woensdag",
		"donderdag",
		"vrijdag",
		"zaterdag"
	],
	"field-zone": "Zone",
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
	"dateFormatItem-yyMM": "MM-yy",
	"days-format-abbr": [
		"zo",
		"ma",
		"di",
		"wo",
		"do",
		"vr",
		"za"
	],
	"eraNames": [
		"Voor Christus",
		"na Christus"
	],
	"days-format-narrow": [
		"Z",
		"M",
		"D",
		"W",
		"D",
		"V",
		"Z"
	],
	"field-month": "Maand",
	"days-standAlone-narrow": [
		"Z",
		"M",
		"D",
		"W",
		"D",
		"V",
		"Z"
	],
	"dateFormatItem-MMM": "LLL",
	"dayPeriods-format-wide-am": "AM",
	"dateFormat-short": "dd-MM-yy",
	"dateFormatItem-MMd": "d-MM",
	"field-second": "Seconde",
	"dateFormatItem-yMMMEd": "EEE d MMM y",
	"dateFormatItem-Ed": "E d",
	"field-week": "Week",
	"dateFormat-medium": "d MMM y"
}
//end v1.x content
);
},
'dojo/cldr/nls/nl-nl/gregorian':function(){
define('dojo/cldr/nls/nl-nl/gregorian',{});
},
'dojo/cldr/nls/nl/number':function(){
define(
"dojo/cldr/nls/nl/number", //begin v1.x content
{
	"group": ".",
	"percentSign": "%",
	"exponential": "E",
	"scientificFormat": "#E0",
	"percentFormat": "#,##0%",
	"list": ";",
	"infinity": "∞",
	"patternDigit": "#",
	"minusSign": "-",
	"decimal": ",",
	"nan": "NaN",
	"nativeZeroDigit": "0",
	"perMille": "‰",
	"decimalFormat": "#,##0.###",
	"currencyFormat": "¤ #,##0.00;¤ #,##0.00-",
	"plusSign": "+"
}
//end v1.x content
);
},
'dojo/cldr/nls/nl-nl/number':function(){
define('dojo/cldr/nls/nl-nl/number',{});
},
'dojox/grid/enhanced/nls/nl/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/nl/EnhancedGrid", //begin v1.x content
({
	singleSort: "Enkelvoudig sorteren",
	nestedSort: "Genest sorteren",
	ascending: "Oplopend",
	descending: "Aflopend",
	sortingState: "${0} - ${1}",
	unsorted: "Deze kolom niet sorteren",
	indirectSelectionRadio: "Rij ${0}, enkele selectie, keuzerondje",
	indirectSelectionCheckBox: "Rij ${0}, meerdere selecties, selectievakje",
	selectAll: "Alles selecteren"
})
//end v1.x content
);


},
'dojox/grid/enhanced/nls/nl-nl/EnhancedGrid':function(){
define('dojox/grid/enhanced/nls/nl-nl/EnhancedGrid',{});
},
'dijit/_editor/nls/nl/commands':function(){
define(
"dijit/_editor/nls/nl/commands", //begin v1.x content
({
	'bold': 'Vet',
	'copy': 'Kopiëren',
	'cut': 'Knippen',
	'delete': 'Wissen',
	'indent': 'Inspringen',
	'insertHorizontalRule': 'Horizontale liniaal',
	'insertOrderedList': 'Genummerde lijst',
	'insertUnorderedList': 'Lijst met opsommingstekens',
	'italic': 'Cursief',
	'justifyCenter': 'Centreren',
	'justifyFull': 'Uitvullen',
	'justifyLeft': 'Links uitlijnen',
	'justifyRight': 'Rechts uitlijnen',
	'outdent': 'Uitspringen',
	'paste': 'Plakken',
	'redo': 'Opnieuw',
	'removeFormat': 'Opmaak verwijderen',
	'selectAll': 'Alles selecteren',
	'strikethrough': 'Doorhalen',
	'subscript': 'Subscript',
	'superscript': 'Superscript',
	'underline': 'Onderstrepen',
	'undo': 'Ongedaan maken',
	'unlink': 'Link verwijderen',
	'createLink': 'Link maken',
	'toggleDir': 'Schrijfrichting wijzigen',
	'insertImage': 'Afbeelding invoegen',
	'insertTable': 'Tabel invoegen/bewerken',
	'toggleTableBorder': 'Tabelkader wijzigen',
	'deleteTable': 'Tabel wissen',
	'tableProp': 'Tabeleigenschap',
	'htmlToggle': 'HTML-bron',
	'foreColor': 'Voorgrondkleur',
	'hiliteColor': 'Achtergrondkleur',
	'plainFormatBlock': 'Alineastijl',
	'formatBlock': 'Alineastijl',
	'fontSize': 'Lettergrootte',
	'fontName': 'Lettertype',
	'tabIndent': 'Inspringen',
	"fullScreen": "Volledig scherm in-/uitschakelen",
	"viewSource": "HTML-bron bekijken",
	"print": "Afdrukken",
	"newPage": "Nieuwe pagina",
	/* Error messages */
	'systemShortcut': 'De actie "${0}" is alleen beschikbaar in uw browser via een sneltoetscombinatie. Gebruik ${1}.'
})
//end v1.x content
);

},
'dijit/_editor/nls/nl-nl/commands':function(){
define('dijit/_editor/nls/nl-nl/commands',{});
},
'dojox/grid/enhanced/nls/nl/Pagination':function(){
define(
"dojox/grid/enhanced/nls/nl/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} van ${1} ${0}",
	"firstTip": "Eerste pagina",
	"lastTip": "Laatste pagina",
	"nextTip": "Volgende pagina",
	"prevTip": "Vorige pagina",
	"itemTitle": "items",
	"singularItemTitle": "item",
	"pageStepLabelTemplate": "Pagina ${0}",
	"pageSizeLabelTemplate": "${0} items per pagina",
	"allItemsLabelTemplate": "Alle items",
	"gotoButtonTitle": "Ga naar bepaalde pagina",
	"dialogTitle": "Ga naar pagina",
	"dialogIndication": "Geef het paginanummer op",
	"pageCountIndication": " (${0} pagina's)",
	"dialogConfirm": "Go",
	"dialogCancel": "Annuleren",
	"all": "alle"
})
//end v1.x content
);


},
'dojox/grid/enhanced/nls/nl-nl/Pagination':function(){
define('dojox/grid/enhanced/nls/nl-nl/Pagination',{});
},
'dijit/form/nls/nl/validate':function(){
define(
"dijit/form/nls/nl/validate", //begin v1.x content
({
	invalidMessage: "De opgegeven waarde is ongeldig.",
	missingMessage: "Deze waarde is verplicht.",
	rangeMessage: "Deze waarde is niet toegestaan."
})
//end v1.x content
);

},
'dijit/form/nls/nl-nl/validate':function(){
define('dijit/form/nls/nl-nl/validate',{});
},
'dojo/cldr/nls/nl/currency':function(){
define(
"dojo/cldr/nls/nl/currency", //begin v1.x content
{
	"HKD_displayName": "Hongkongse dollar",
	"CHF_displayName": "Zwitserse franc",
	"CAD_displayName": "Canadese dollar",
	"CNY_displayName": "Chinese yuan renminbi",
	"AUD_displayName": "Australische dollar",
	"JPY_displayName": "Japanse yen",
	"USD_displayName": "Amerikaanse dollar",
	"GBP_displayName": "Brits pond sterling",
	"EUR_displayName": "Euro"
}
//end v1.x content
);
},
'dojo/cldr/nls/nl-nl/currency':function(){
define('dojo/cldr/nls/nl-nl/currency',{});
},
'dijit/form/nls/nl/ComboBox':function(){
define(
"dijit/form/nls/nl/ComboBox", //begin v1.x content
({
		previousMessage: "Eerdere opties",
		nextMessage: "Meer opties"
})
//end v1.x content
);

},
'dijit/form/nls/nl-nl/ComboBox':function(){
define('dijit/form/nls/nl-nl/ComboBox',{});
},
'dijit/nls/nl/loading':function(){
define(
"dijit/nls/nl/loading", //begin v1.x content
({
	loadingState: "Bezig met laden...",
	errorState: "Er is een fout opgetreden"
})
//end v1.x content
);

},
'dijit/nls/nl-nl/loading':function(){
define('dijit/nls/nl-nl/loading',{});
}}});
define("dojo/nls/freenasdojo_nl-nl", [], 1);
