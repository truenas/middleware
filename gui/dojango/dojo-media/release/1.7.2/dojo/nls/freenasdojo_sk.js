require({cache:{
'dojox/form/nls/sk/CheckedMultiSelect':function(){
define(
"dojox/form/nls/sk/CheckedMultiSelect", ({
	invalidMessage: "Musíte vybrať aspoň jednu položku.",
	multiSelectLabelText: "Vybraté položky: {num}"
})
);

},
'dijit/nls/sk/common':function(){
define(
"dijit/nls/sk/common", //begin v1.x content
({
	buttonOk: "OK",
	buttonCancel: "Zrušiť",
	buttonSave: "Uložiť",
	itemClose: "Zatvoriť"
})

//end v1.x content
);

},
'dojox/grid/enhanced/nls/sk/Filter':function(){
define(
"dojox/grid/enhanced/nls/sk/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "Zrušiť filter",
	"filterDefDialogTitle": "Filter",
	"ruleTitleTemplate": "Pravidlo ${0}",
	
	"conditionEqual": "rovné",
	"conditionNotEqual": "nerovné",
	"conditionLess": "menšie ako",
	"conditionLessEqual": "menšie ako alebo rovné",
	"conditionLarger": "väčšie ako",
	"conditionLargerEqual": "väčšie ako alebo rovné",
	"conditionContains": "obsahuje",
	"conditionIs": "je",
	"conditionStartsWith": "začína s",
	"conditionEndWith": "končí s",
	"conditionNotContain": "neobsahuje",
	"conditionIsNot": "nie je",
	"conditionNotStartWith": "nezačína s",
	"conditionNotEndWith": "nekončí s",
	"conditionBefore": "pred",
	"conditionAfter": "za",
	"conditionRange": "rozsah",
	"conditionIsEmpty": "je prázdne",
	
	"all": "všetko",
	"any": "žiadne",
	"relationAll": "všetky pravidlá",
	"waiRelAll": "Vyhovovať všetkým týmto pravidlám:",
	"relationAny": "ľubovoľné pravidlá",
	"waiRelAny": "Vyhovovať ľubovoľným z týchto pravidiel:",
	"relationMsgFront": "Vyhovieť",
	"relationMsgTail": "",
	"and": "a",
	"or": "alebo",
	
	"addRuleButton": "Pridať pravidlo",
	"waiAddRuleButton": "Pridať nové pravidlo",
	"removeRuleButton": "Odstrániť pravidlo",
	"waiRemoveRuleButtonTemplate": "Odstrániť pravidlo ${0}",
	
	"cancelButton": "Zrušiť",
	"waiCancelButton": "Zrušiť toto dialógové okno",
	"clearButton": "Zrušiť",
	"waiClearButton": "Zrušiť filter",
	"filterButton": "Filtrovať",
	"waiFilterButton": "Odoslať filter",
	
	"columnSelectLabel": "Stĺpec",
	"waiColumnSelectTemplate": "Stĺpec pre pravidlo ${0}",
	"conditionSelectLabel": "Podmienka",
	"waiConditionSelectTemplate": "Podmienka pre pravidlo ${0}",
	"valueBoxLabel": "Hodnota",
	"waiValueBoxTemplate": "Zadajte hodnotu na filtrovanie pre pravidlo ${0}",
	
	"rangeTo": "do",
	"rangeTemplate": "od ${0} do ${1}",
	
	"statusTipHeaderColumn": "Stĺpec",
	"statusTipHeaderCondition": "Pravidlá",
	"statusTipTitle": "Lišta filtra",
	"statusTipMsg": "Kliknite na lištu filtra, ak chcete filtrovať podľa hodnôt v ${0}.",
	"anycolumn": "ľubovoľný stĺpec",
	"statusTipTitleNoFilter": "Lišta filtra",
	"statusTipTitleHasFilter": "Filter",
	"statusTipRelAny": "Zhoda s akýmikoľvek pravidlami.",
	"statusTipRelAll": "Zhoda so všetkými pravidlami.",
	
	"defaultItemsName": "položky",
	"filterBarMsgHasFilterTemplate": "Zobrazuje sa ${0} z ${1} ${2}.",
	"filterBarMsgNoFilterTemplate": "Nepoužíva sa žiadny filter",
	
	"filterBarDefButton": "Definovať filter",
	"waiFilterBarDefButton": "Filtrovať tabuľku",
	"a11yFilterBarDefButton": "Filtrovať...",
	"filterBarClearButton": "Zrušiť filter",
	"waiFilterBarClearButton": "Zrušiť filter",
	"closeFilterBarBtn": "Zatvoriť lištu filtra",
	
	"clearFilterMsg": "Toto odstráni filter a zobrazí všetky dostupné záznamy",
	"anyColumnOption": "Ľubovoľný stĺpec",
	
	"trueLabel": "Pravda",
	"falseLabel": "Nepravda"
})
//end v1.x content
);

},
'dojo/cldr/nls/sk/gregorian':function(){
define(
"dojo/cldr/nls/sk/gregorian", //begin v1.x content
{
	"field-dayperiod": "Časť dňa",
	"dateFormatItem-yQ": "Q yyyy",
	"dayPeriods-format-wide-pm": "popoludní",
	"field-minute": "Minúta",
	"eraNames": [
		"pred n.l.",
		"n.l."
	],
	"dateFormatItem-MMMEd": "E, d. MMM",
	"field-day-relative+-1": "Včera",
	"field-weekday": "Deň v týždni",
	"dateFormatItem-yQQQ": "QQQ y",
	"field-day-relative+-2": "Predvčerom",
	"field-day-relative+-3": "Pred tromi dňami",
	"days-standAlone-wide": [
		"nedeľa",
		"pondelok",
		"utorok",
		"streda",
		"štvrtok",
		"piatok",
		"sobota"
	],
	"months-standAlone-narrow": [
		"j",
		"f",
		"m",
		"a",
		"m",
		"j",
		"j",
		"a",
		"s",
		"o",
		"n",
		"d"
	],
	"field-era": "Éra",
	"field-hour": "Hodina",
	"dayPeriods-format-wide-am": "dopoludnia",
	"timeFormat-full": "H:mm:ss zzzz",
	"months-standAlone-abbr": [
		"jan",
		"feb",
		"mar",
		"apr",
		"máj",
		"jún",
		"júl",
		"aug",
		"sep",
		"okt",
		"nov",
		"dec"
	],
	"dateFormatItem-yMMM": "LLL y",
	"field-day-relative+0": "Dnes",
	"field-day-relative+1": "Zajtra",
	"days-standAlone-narrow": [
		"N",
		"P",
		"U",
		"S",
		"Š",
		"P",
		"S"
	],
	"eraAbbr": [
		"pred n.l.",
		"n.l."
	],
	"field-day-relative+2": "Pozajtra",
	"field-day-relative+3": "O tri dni",
	"dateFormatItem-yyyyMMMM": "LLLL y",
	"dateFormat-long": "d. MMMM y",
	"timeFormat-medium": "H:mm:ss",
	"dateFormatItem-EEEd": "EEE, d.",
	"field-zone": "Pásmo",
	"dateFormatItem-Hm": "H:mm",
	"dateFormat-medium": "d.M.yyyy",
	"dateFormatItem-Hms": "H:mm:ss",
	"dateFormatItem-yyQQQQ": "QQQQ yy",
	"quarters-standAlone-wide": [
		"1. štvrťrok",
		"2. štvrťrok",
		"3. štvrťrok",
		"4. štvrťrok"
	],
	"dateFormatItem-yMMMM": "LLLL y",
	"dateFormatItem-ms": "mm:ss",
	"field-year": "Rok",
	"months-standAlone-wide": [
		"január",
		"február",
		"marec",
		"apríl",
		"máj",
		"jún",
		"júl",
		"august",
		"september",
		"október",
		"november",
		"december"
	],
	"field-week": "Týždeň",
	"dateFormatItem-MMMMEd": "E, d. MMMM",
	"dateFormatItem-MMMd": "d. MMM",
	"dateFormatItem-yyQ": "Q yy",
	"timeFormat-long": "H:mm:ss z",
	"months-format-abbr": [
		"jan",
		"feb",
		"mar",
		"apr",
		"máj",
		"jún",
		"júl",
		"aug",
		"sep",
		"okt",
		"nov",
		"dec"
	],
	"timeFormat-short": "H:mm",
	"dateFormatItem-H": "H",
	"field-month": "Mesiac",
	"dateFormatItem-MMMMd": "d. MMMM",
	"quarters-format-abbr": [
		"Q1",
		"Q2",
		"Q3",
		"Q4"
	],
	"days-format-abbr": [
		"ne",
		"po",
		"ut",
		"st",
		"št",
		"pi",
		"so"
	],
	"dateFormatItem-mmss": "mm:ss",
	"days-format-narrow": [
		"N",
		"P",
		"U",
		"S",
		"Š",
		"P",
		"S"
	],
	"field-second": "Sekunda",
	"field-day": "Deň",
	"dateFormatItem-MEd": "E, d.M.",
	"months-format-narrow": [
		"j",
		"f",
		"m",
		"a",
		"m",
		"j",
		"j",
		"a",
		"s",
		"o",
		"n",
		"d"
	],
	"days-standAlone-abbr": [
		"ne",
		"po",
		"ut",
		"st",
		"št",
		"pi",
		"so"
	],
	"dateFormat-short": "d.M.yyyy",
	"dateFormatItem-yyyyM": "M.yyyy",
	"dateFormatItem-yMMMEd": "EEE, d. MMM y",
	"dateFormat-full": "EEEE, d. MMMM y",
	"dateFormatItem-Md": "d.M.",
	"dateFormatItem-yMEd": "EEE, d.M.yyyy",
	"months-format-wide": [
		"januára",
		"februára",
		"marca",
		"apríla",
		"mája",
		"júna",
		"júla",
		"augusta",
		"septembra",
		"októbra",
		"novembra",
		"decembra"
	],
	"dateFormatItem-d": "d.",
	"quarters-format-wide": [
		"1. štvrťrok",
		"2. štvrťrok",
		"3. štvrťrok",
		"4. štvrťrok"
	],
	"days-format-wide": [
		"nedeľa",
		"pondelok",
		"utorok",
		"streda",
		"štvrtok",
		"piatok",
		"sobota"
	],
	"eraNarrow": [
		"pred n.l.",
		"n.l."
	]
}
//end v1.x content
);
},
'dojo/cldr/nls/sk/number':function(){
define(
"dojo/cldr/nls/sk/number", //begin v1.x content
{
	"currencyFormat": "#,##0.00 ¤",
	"group": " ",
	"decimal": ","
}
//end v1.x content
);
},
'dojox/grid/enhanced/nls/sk/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/sk/EnhancedGrid", //begin v1.x content
({
	singleSort: "Jednoduché triedenie",
	nestedSort: "Vnorené triedenie",
	ascending: "Vzostupne",
	descending: "Zostupne",
	sortingState: "${0} - ${1}",
	unsorted: "Netriediť tento stĺpec",
	indirectSelectionRadio: "Riadok ${0}, jednoduchý výber, prepínač",
	indirectSelectionCheckBox: "Riadok ${0}, viacnásobný výber, začiarkavacie políčko",
	selectAll: "Vybrať všetko"
})
//end v1.x content
);


},
'dijit/_editor/nls/sk/commands':function(){
define(
"dijit/_editor/nls/sk/commands", //begin v1.x content
({
	'bold': 'Tučné písmo',
	'copy': 'Kopírovať',
	'cut': 'Vystrihnúť',
	'delete': 'Vymazať',
	'indent': 'Odsadiť',
	'insertHorizontalRule': 'Horizontálna čiara',
	'insertOrderedList': 'Číslovaný zoznam',
	'insertUnorderedList': 'Zoznam s odrážkami',
	'italic': 'Kurzíva',
	'justifyCenter': 'Zarovnať na stred',
	'justifyFull': 'Zarovnať podľa okraja',
	'justifyLeft': 'Zarovnať doľava',
	'justifyRight': 'Zarovnať doprava',
	'outdent': 'Predsadiť',
	'paste': 'Nalepiť',
	'redo': 'Znova vykonať',
	'removeFormat': 'Odstrániť formát',
	'selectAll': 'Vybrať všetko',
	'strikethrough': 'Prečiarknuť',
	'subscript': 'Dolný index',
	'superscript': 'Horný index',
	'underline': 'Podčiarknuť',
	'undo': 'Vrátiť späť',
	'unlink': 'Odstrániť prepojenie',
	'createLink': 'Vytvoriť prepojenie',
	'toggleDir': 'Prepnúť smer',
	'insertImage': 'Vložiť obrázok',
	'insertTable': 'Vložiť/upraviť tabuľku',
	'toggleTableBorder': 'Prepnúť rámček tabuľky',
	'deleteTable': 'Vymazať tabuľku',
	'tableProp': 'Vlastnosť tabuľky',
	'htmlToggle': 'Zdroj HTML',
	'foreColor': 'Farba popredia',
	'hiliteColor': 'Farba pozadia',
	'plainFormatBlock': 'Štýl odseku',
	'formatBlock': 'Štýl odseku',
	'fontSize': 'Veľkosť písma',
	'fontName': 'Názov písma',
	'tabIndent': 'Odsadenie tabulátora',
	"fullScreen": "Zobraziť na celú obrazovku",
	"viewSource": "Zobraziť zdrojový kód HTML ",
	"print": "Tlačiť",
	"newPage": "Nová stránka ",
	/* Error messages */
	'systemShortcut': 'Akcia "${0}" je vo vašom prehliadači dostupná len s použitím klávesovej skratky. Použite ${1}.'
})

//end v1.x content
);

},
'dojox/grid/enhanced/nls/sk/Pagination':function(){
define(
"dojox/grid/enhanced/nls/sk/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} z ${1} ${0}",
	"firstTip": "Prvá strana",
	"lastTip": "Posledná strana",
	"nextTip": "Ďalšia strana",
	"prevTip": "Predošlá strana",
	"itemTitle": "položiek",
	"singularItemTitle": "položka",
	"pageStepLabelTemplate": "Strana ${0}",
	"pageSizeLabelTemplate": "${0} položiek na strane",
	"allItemsLabelTemplate": "Všetky položky",
	"gotoButtonTitle": "Prejsť na špecifickú stranu",
	"dialogTitle": "Prejsť na stranu",
	"dialogIndication": "Zadajte číslo strany",
	"pageCountIndication": " (${0} strán)",
	"dialogConfirm": "Prejsť",
	"dialogCancel": "Zrušiť",
	"all": "všetko"
})
//end v1.x content
);

},
'dijit/form/nls/sk/validate':function(){
define(
"dijit/form/nls/sk/validate", //begin v1.x content
({
	invalidMessage: "Zadaná hodnota nie je platná.",
	missingMessage: "Táto hodnota je vyžadovaná.",
	rangeMessage: "Táto hodnota je mimo rozsah."
})

//end v1.x content
);

},
'dojo/cldr/nls/sk/currency':function(){
define(
"dojo/cldr/nls/sk/currency", //begin v1.x content
{
	"HKD_displayName": "Hong Kongský dolár",
	"CHF_displayName": "Švajčiarský frank",
	"CAD_displayName": "Kanadský dolár",
	"CNY_displayName": "Čínsky Yuan Renminbi",
	"AUD_displayName": "Austrálsky dolár",
	"JPY_displayName": "Japonský yen",
	"USD_displayName": "US dolár",
	"GBP_displayName": "Britská libra",
	"EUR_displayName": "Euro"
}
//end v1.x content
);
},
'dijit/form/nls/sk/ComboBox':function(){
define(
"dijit/form/nls/sk/ComboBox", //begin v1.x content
({
		previousMessage: "Predchádzajúce voľby",
		nextMessage: "Ďalšie voľby"
})

//end v1.x content
);

},
'dijit/nls/sk/loading':function(){
define(
"dijit/nls/sk/loading", //begin v1.x content
({
	loadingState: "Zavádzanie...",
	errorState: "Nastala chyba"
})

//end v1.x content
);

}}});
define("dojo/nls/freenasdojo_sk", [], 1);
