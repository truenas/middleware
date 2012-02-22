require({cache:{
'dojox/form/nls/sl/CheckedMultiSelect':function(){
define(
"dojox/form/nls/sl/CheckedMultiSelect", ({
	invalidMessage: "Izbrati morate vsaj eno postavko.",
	multiSelectLabelText: "Število izbranih postavk: {num}"
})
);

},
'dijit/nls/sl/common':function(){
define(
"dijit/nls/sl/common", //begin v1.x content
({
	buttonOk: "V redu",
	buttonCancel: "Prekliči",
	buttonSave: "Shrani",
	itemClose: "Zapri"
})

//end v1.x content
);

},
'dojox/grid/enhanced/nls/sl/Filter':function(){
define(
"dojox/grid/enhanced/nls/sl/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "Počisti filter",
	"filterDefDialogTitle": "Filter",
	"ruleTitleTemplate": "Pravilo ${0}",
	
	"conditionEqual": "je enako",
	"conditionNotEqual": "ni enako",
	"conditionLess": "je manjše kot",
	"conditionLessEqual": "je manjše kot ali enako",
	"conditionLarger": "je večje kot",
	"conditionLargerEqual": "je večje kot ali enako",
	"conditionContains": "vsebuje",
	"conditionIs": "je",
	"conditionStartsWith": "se začne s",
	"conditionEndWith": "se konča s",
	"conditionNotContain": "ne vsebuje",
	"conditionIsNot": "ni",
	"conditionNotStartWith": "se ne začne s",
	"conditionNotEndWith": "se ne konča s",
	"conditionBefore": "pred",
	"conditionAfter": "za",
	"conditionRange": "obseg",
	"conditionIsEmpty": "je prazno",
	
	"all": "vse",
	"any": "karkoli",
	"relationAll": "vsa pravila",
	"waiRelAll": "Ujema se z vsemi od naslednjih pravil:",
	"relationAny": "katerakoli pravila",
	"waiRelAny": "Ujema se s katerimkoli od naslednjih pravil:",
	"relationMsgFront": "Ujemanje",
	"relationMsgTail": "",
	"and": "in",
	"or": "ali",
	
	"addRuleButton": "Dodaj pravilo",
	"waiAddRuleButton": "Dodaj novo pravilo",
	"removeRuleButton": "Odstrani pravilo",
	"waiRemoveRuleButtonTemplate": "Odstrani pravilo ${0}",
	
	"cancelButton": "Prekliči",
	"waiCancelButton": "Prekliči to pogovorno okno",
	"clearButton": "Počisti",
	"waiClearButton": "Počisti filter",
	"filterButton": "Filter",
	"waiFilterButton": "Predloži filter",
	
	"columnSelectLabel": "Stolpec",
	"waiColumnSelectTemplate": "Stolpec za pravilo ${0}",
	"conditionSelectLabel": "Pogoj",
	"waiConditionSelectTemplate": "Pogoj za pravilo ${0}",
	"valueBoxLabel": "Vrednost",
	"waiValueBoxTemplate": "Vnesite vrednost za filter pravila ${0}",
	
	"rangeTo": "do",
	"rangeTemplate": "od ${0} do ${1}",
	
	"statusTipHeaderColumn": "Stolpec",
	"statusTipHeaderCondition": "Pravila",
	"statusTipTitle": "Vrstica za filtriranje",
	"statusTipMsg": "Kliknite vrstico za filtriranje tukaj, da prefiltrirate vrednosti v ${0}.",
	"anycolumn": "katerikoli stolpec",
	"statusTipTitleNoFilter": "Vrstica za filtriranje",
	"statusTipTitleHasFilter": "Filter",
	"statusTipRelAny": "Ujemanje s katerimkoli pravilom.",
	"statusTipRelAll": "Ujemanje z vsemi pravili.",
	
	"defaultItemsName": "postavke",
	"filterBarMsgHasFilterTemplate": "Prikazanih je ${0} od ${1} ${2}.",
	"filterBarMsgNoFilterTemplate": "Uveljavljen ni noben filter.",
	
	"filterBarDefButton": "Definiraj filter",
	"waiFilterBarDefButton": "Filtriraj tabelo",
	"a11yFilterBarDefButton": "Filtriraj ...",
	"filterBarClearButton": "Počisti filter",
	"waiFilterBarClearButton": "Počisti filter",
	"closeFilterBarBtn": "Zapri vrstico za filtriranje",
	
	"clearFilterMsg": "S tem boste odstranili filter in prikazali se bodo vsi razpoložljivi zapisi.",
	"anyColumnOption": "Katerikoli stolpec",
	
	"trueLabel": "True",
	"falseLabel": "False"
})
//end v1.x content
);

},
'dojo/cldr/nls/sl/gregorian':function(){
define(
"dojo/cldr/nls/sl/gregorian", //begin v1.x content
{
	"field-dayperiod": "Čas dneva",
	"dayPeriods-format-wide-pm": "pop.",
	"field-minute": "Minuta",
	"eraNames": [
		"pred našim štetjem",
		"naše štetje"
	],
	"dateFormatItem-MMMEd": "E., d. MMM",
	"field-day-relative+-1": "Včeraj",
	"field-weekday": "Dan v tednu",
	"field-day-relative+-2": "Predvčerajšnjim",
	"field-day-relative+-3": "Pred tremi dnevi",
	"days-standAlone-wide": [
		"nedelja",
		"ponedeljek",
		"torek",
		"sreda",
		"četrtek",
		"petek",
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
	"field-era": "Doba",
	"field-hour": "Ura",
	"dayPeriods-format-wide-am": "dop.",
	"dateFormatItem-y": "y",
	"timeFormat-full": "HH:mm:ss zzzz",
	"months-standAlone-abbr": [
		"jan",
		"feb",
		"mar",
		"apr",
		"maj",
		"jun",
		"jul",
		"avg",
		"sep",
		"okt",
		"nov",
		"dec"
	],
	"dateFormatItem-Ed": "E., d.",
	"dateFormatItem-yMMM": "MMM y",
	"field-day-relative+0": "Danes",
	"field-day-relative+1": "Jutri",
	"days-standAlone-narrow": [
		"n",
		"p",
		"t",
		"s",
		"č",
		"p",
		"s"
	],
	"eraAbbr": [
		"pr. n. št.",
		"po Kr."
	],
	"field-day-relative+2": "Pojutrišnjem",
	"field-day-relative+3": "Čez tri dni",
	"dateFormatItem-yyyyMMMM": "MMMM y",
	"dateFormat-long": "dd. MMMM y",
	"timeFormat-medium": "HH:mm:ss",
	"field-zone": "Območje",
	"dateFormatItem-Hm": "HH:mm",
	"dateFormat-medium": "d. MMM yyyy",
	"dateFormatItem-Hms": "HH:mm:ss",
	"quarters-standAlone-wide": [
		"1. četrtletje",
		"2. četrtletje",
		"3. četrtletje",
		"4. četrtletje"
	],
	"dateFormatItem-ms": "mm:ss",
	"field-year": "Leto",
	"field-week": "Teden",
	"months-standAlone-wide": [
		"januar",
		"februar",
		"marec",
		"april",
		"maj",
		"junij",
		"julij",
		"avgust",
		"september",
		"oktober",
		"november",
		"december"
	],
	"dateFormatItem-MMMd": "d. MMM",
	"dateFormatItem-yyQ": "Q/yy",
	"timeFormat-long": "HH:mm:ss z",
	"months-format-abbr": [
		"jan.",
		"feb.",
		"mar.",
		"apr.",
		"maj",
		"jun.",
		"jul.",
		"avg.",
		"sep.",
		"okt.",
		"nov.",
		"dec."
	],
	"timeFormat-short": "HH:mm",
	"field-month": "Mesec",
	"quarters-format-abbr": [
		"Q1",
		"Q2",
		"Q3",
		"Q4"
	],
	"days-format-abbr": [
		"ned",
		"pon",
		"tor",
		"sre",
		"čet",
		"pet",
		"sob"
	],
	"dateFormatItem-mmss": "mm:ss",
	"days-format-narrow": [
		"n",
		"p",
		"t",
		"s",
		"č",
		"p",
		"s"
	],
	"field-second": "Sekunda",
	"field-day": "Dan",
	"dateFormatItem-MEd": "E., d. MM.",
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
		"ned",
		"pon",
		"tor",
		"sre",
		"čet",
		"pet",
		"sob"
	],
	"dateFormat-short": "d. MM. yy",
	"dateFormatItem-yyyyM": "M/yyyy",
	"dateFormatItem-yMMMEd": "E., d. MMM y",
	"dateFormat-full": "EEEE, dd. MMMM y",
	"dateFormatItem-Md": "d. M.",
	"dateFormatItem-yMEd": "E., d. M. y",
	"months-format-wide": [
		"januar",
		"februar",
		"marec",
		"april",
		"maj",
		"junij",
		"julij",
		"avgust",
		"september",
		"oktober",
		"november",
		"december"
	],
	"quarters-format-wide": [
		"1. četrtletje",
		"2. četrtletje",
		"3. četrtletje",
		"4. četrtletje"
	],
	"days-format-wide": [
		"nedelja",
		"ponedeljek",
		"torek",
		"sreda",
		"četrtek",
		"petek",
		"sobota"
	],
	"eraNarrow": [
		"pr. n. št.",
		"po Kr."
	]
}
//end v1.x content
);
},
'dojo/cldr/nls/sl/number':function(){
define(
"dojo/cldr/nls/sl/number", //begin v1.x content
{
	"group": ".",
	"percentSign": "%",
	"exponential": "e",
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
	"currencyFormat": "#,##0.00 ¤",
	"plusSign": "+"
}
//end v1.x content
);
},
'dojox/grid/enhanced/nls/sl/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/sl/EnhancedGrid", //begin v1.x content
({
	singleSort: "Enostavno razvrščanje",
	nestedSort: "Ugnezdeno razvrščanje",
	ascending: "Naraščajoče",
	descending: "Padajoče",
	sortingState: "${0} - ${1}",
	unsorted: "Ne razvrščaj tega stolpca",
	indirectSelectionRadio: "Vrstica ${0}, izbira enega elementa, okence z izbirnim gumbom",
	indirectSelectionCheckBox: "Vrstica ${0}, izbira več elementov, okence s potrditvenimi polji",
	selectAll: "Izberi vse"
})
//end v1.x content
);


},
'dijit/_editor/nls/sl/commands':function(){
define(
"dijit/_editor/nls/sl/commands", //begin v1.x content
({
	'bold': 'Krepko',
	'copy': 'Prekopiraj',
	'cut': 'Izreži',
	'delete': 'Izbriši',
	'indent': 'Zamik',
	'insertHorizontalRule': 'Vodoravno ravnilo',
	'insertOrderedList': 'Oštevilčen seznam',
	'insertUnorderedList': 'Naštevni seznam',
	'italic': 'Ležeče',
	'justifyCenter': 'Poravnaj na sredino',
	'justifyFull': 'Poravnaj obojestransko',
	'justifyLeft': 'Poravnaj levo',
	'justifyRight': 'Poravnaj desno',
	'outdent': 'Primakni',
	'paste': 'Prilepi',
	'redo': 'Znova uveljavi',
	'removeFormat': 'Odstrani oblikovanje',
	'selectAll': 'Izberi vse',
	'strikethrough': 'Prečrtano',
	'subscript': 'Podpisano',
	'superscript': 'Nadpisano',
	'underline': 'Podčrtano',
	'undo': 'Razveljavi',
	'unlink': 'Odstrani povezavo',
	'createLink': 'Ustvari povezavo',
	'toggleDir': 'Preklopi smer',
	'insertImage': 'Vstavi sliko',
	'insertTable': 'Vstavi/uredi tabelo',
	'toggleTableBorder': 'Preklopi na rob tabele',
	'deleteTable': 'Izbriši tabelo',
	'tableProp': 'Lastnost tabele',
	'htmlToggle': 'Izvorna koda HTML',
	'foreColor': 'Barva ospredja',
	'hiliteColor': 'Barva ozadja',
	'plainFormatBlock': 'Slog odstavka',
	'formatBlock': 'Slog odstavka',
	'fontSize': 'Velikost pisave',
	'fontName': 'Ime pisave',
	'tabIndent': 'Zamik tabulatorja',
	"fullScreen": "Preklopi na celozaslonski način",
	"viewSource": "Prikaži izvorno kodo HTML",
	"print": "Natisni",
	"newPage": "Nova stran",
	/* Error messages */
	'systemShortcut': 'Dejanje "${0}" lahko v vašem brskalniku uporabite samo z bližnjico na tipkovnici. Uporabite ${1}.'
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/sl/Pagination':function(){
define(
"dojox/grid/enhanced/nls/sl/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} od ${1} ${0}",
	"firstTip": "Prva stran",
	"lastTip": "Zadnja stran",
	"nextTip": "Naslednja stran",
	"prevTip": "Prejšnja stran",
	"itemTitle": "postavke",
	"singularItemTitle": "postavka",
	"pageStepLabelTemplate": "Stran ${0}",
	"pageSizeLabelTemplate": "${0} postavk na stran",
	"allItemsLabelTemplate": "Vse postavke",
	"gotoButtonTitle": "Pojdi na specifično stran",
	"dialogTitle": "Pojdi na stran",
	"dialogIndication": "Podajte številko strani",
	"pageCountIndication": " (${0} strani)",
	"dialogConfirm": "Pojdi",
	"dialogCancel": "Prekliči",
	"all": "vse"
})
//end v1.x content
);


},
'dijit/form/nls/sl/validate':function(){
define(
"dijit/form/nls/sl/validate", //begin v1.x content
({
	invalidMessage: "Vnesena vrednost ni veljavna.",
	missingMessage: "Ta vrednost je zahtevana.",
	rangeMessage: "Ta vrednost je izven območja."
})

//end v1.x content
);

},
'dojo/cldr/nls/sl/currency':function(){
define(
"dojo/cldr/nls/sl/currency", //begin v1.x content
{
	"HKD_displayName": "hongkonški dolar",
	"CHF_displayName": "švicarski frank",
	"JPY_symbol": "¥",
	"CAD_displayName": "kanadski dolar",
	"CNY_displayName": "kitajski juan renminbi",
	"USD_symbol": "$",
	"AUD_displayName": "avstralski dolar",
	"JPY_displayName": "japonski jen",
	"USD_displayName": "ameriški dolar",
	"GBP_displayName": "britanski funt",
	"EUR_displayName": "evro"
}
//end v1.x content
);
},
'dijit/form/nls/sl/ComboBox':function(){
define(
"dijit/form/nls/sl/ComboBox", //begin v1.x content
({
		previousMessage: "Prejšnje izbire",
		nextMessage: "Dodatne izbire"
})

//end v1.x content
);

},
'dijit/nls/sl/loading':function(){
define(
"dijit/nls/sl/loading", //begin v1.x content
({
	loadingState: "Nalaganje ...",
	errorState: "Oprostite, prišlo je do napake."
})
//end v1.x content
);

}}});
define("dojo/nls/freenasdojo_sl", [], 1);
