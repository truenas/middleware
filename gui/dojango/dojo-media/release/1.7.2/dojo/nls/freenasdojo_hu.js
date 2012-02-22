require({cache:{
'dojox/form/nls/hu/CheckedMultiSelect':function(){
define(
"dojox/form/nls/hu/CheckedMultiSelect", ({
	invalidMessage: "Legalább egy tételt ki kell választani.",
	multiSelectLabelText: "{num} elem van kiválasztva"
})
);

},
'dijit/nls/hu/common':function(){
define(
"dijit/nls/hu/common", //begin v1.x content
({
	buttonOk: "OK",
	buttonCancel: "Mégse",
	buttonSave: "Mentés",
	itemClose: "Bezárás"
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/hu/Filter':function(){
define(
"dojox/grid/enhanced/nls/hu/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "Szűrő törlése",
	"filterDefDialogTitle": "Szűrő",
	"ruleTitleTemplate": "${0} szabály",
	
	"conditionEqual": "egyenlő",
	"conditionNotEqual": "nem egyenlő",
	"conditionLess": "kisebb mint",
	"conditionLessEqual": "kisebb vagy egyenlő",
	"conditionLarger": "nagyobb mint",
	"conditionLargerEqual": "nagyobb vagy egyenlő",
	"conditionContains": "tartalmazza",
	"conditionIs": "pontosan",
	"conditionStartsWith": "kezdete",
	"conditionEndWith": "vége",
	"conditionNotContain": "nem tartalmazza",
	"conditionIsNot": "nem",
	"conditionNotStartWith": "nem kezdete",
	"conditionNotEndWith": "nem vége",
	"conditionBefore": "előtt",
	"conditionAfter": "után",
	"conditionRange": "tartomány",
	"conditionIsEmpty": "üres",
	
	"all": "mind",
	"any": "bármely",
	"relationAll": "minden szabály",
	"waiRelAll": "Megfelel a következő összes szabálynak:",
	"relationAny": "bármely szabály",
	"waiRelAny": "Megfelel a következő bármely szabálynak:",
	"relationMsgFront": "Egyezik",
	"relationMsgTail": "",
	"and": "és",
	"or": "vagy",
	
	"addRuleButton": "Szabály hozzáadása",
	"waiAddRuleButton": "Új szabály hozzáadása",
	"removeRuleButton": "Szabály eltávolítása",
	"waiRemoveRuleButtonTemplate": "${0} szabály eltávolítása",
	
	"cancelButton": "Mégse",
	"waiCancelButton": "A párbeszédablak bezárása",
	"clearButton": "Törlés",
	"waiClearButton": "A szűrő törlése",
	"filterButton": "Szűrő",
	"waiFilterButton": "A szűrő elküldése",
	
	"columnSelectLabel": "Oszlop",
	"waiColumnSelectTemplate": "Oszlop a(z) ${0} szabályhoz",
	"conditionSelectLabel": "Feltétel",
	"waiConditionSelectTemplate": "Feltétel a(z) ${0} szabályhoz",
	"valueBoxLabel": "Érték",
	"waiValueBoxTemplate": "Írja be a szűrni kívánt értéket a(z) ${0} szabályhoz",
	
	"rangeTo": "-",
	"rangeTemplate": "${0} - ${1}",
	
	"statusTipHeaderColumn": "Oszlop",
	"statusTipHeaderCondition": "Szabályok",
	"statusTipTitle": "Szűrősáv",
	"statusTipMsg": "Kattintson a szűrősávra az értékek szűréséhez a következőben: ${0}.",
	"anycolumn": "bármely oszlop",
	"statusTipTitleNoFilter": "Szűrősáv",
	"statusTipTitleHasFilter": "Szűrő",
	"statusTipRelAny": "Bármely szabálynak megfelel.",
	"statusTipRelAll": "Minden szabálynak megfelel.",
	
	"defaultItemsName": "elemek",
	"filterBarMsgHasFilterTemplate": "${0} / ${1} ${2} megjelenítve.",
	"filterBarMsgNoFilterTemplate": "Nincs szűrő alkalmazva.",
	
	"filterBarDefButton": "Szűrő meghatározása",
	"waiFilterBarDefButton": "Táblázat szűrése",
	"a11yFilterBarDefButton": "Szűrés...",
	"filterBarClearButton": "Szűrő törlése",
	"waiFilterBarClearButton": "A szűrő törlése",
	"closeFilterBarBtn": "Szűrősáv bezárása",
	
	"clearFilterMsg": "Eltávolítja a szűrőt és megjeleníti az összes elérhető rekordot.",
	"anyColumnOption": "Bármely oszlop",
	
	"trueLabel": "Igaz",
	"falseLabel": "Hamis"
})
//end v1.x content
);

},
'dojo/cldr/nls/hu/gregorian':function(){
define(
"dojo/cldr/nls/hu/gregorian", //begin v1.x content
{
	"field-dayperiod": "napszak",
	"dayPeriods-format-wide-pm": "du.",
	"field-minute": "perc",
	"eraNames": [
		"időszámításunk előtt",
		"időszámításunk szerint"
	],
	"dateFormatItem-MMMEd": "MMM d., E",
	"field-day-relative+-1": "tegnap",
	"field-weekday": "hét napja",
	"field-day-relative+-2": "tegnapelőtt",
	"dateFormatItem-MMdd": "MM.dd.",
	"field-day-relative+-3": "három nappal ezelőtt",
	"days-standAlone-wide": [
		"vasárnap",
		"hétfő",
		"kedd",
		"szerda",
		"csütörtök",
		"péntek",
		"szombat"
	],
	"dateFormatItem-MMM": "LLL",
	"months-standAlone-narrow": [
		"J",
		"F",
		"M",
		"Á",
		"M",
		"J",
		"J",
		"A",
		"Sz",
		"O",
		"N",
		"D"
	],
	"field-era": "éra",
	"field-hour": "óra",
	"dayPeriods-format-wide-am": "de.",
	"quarters-standAlone-abbr": [
		"N1",
		"N2",
		"N3",
		"N4"
	],
	"timeFormat-full": "H:mm:ss zzzz",
	"months-standAlone-abbr": [
		"jan.",
		"febr.",
		"márc.",
		"ápr.",
		"máj.",
		"jún.",
		"júl.",
		"aug.",
		"szept.",
		"okt.",
		"nov.",
		"dec."
	],
	"dateFormatItem-Ed": "d., E",
	"field-day-relative+0": "ma",
	"field-day-relative+1": "holnap",
	"days-standAlone-narrow": [
		"V",
		"H",
		"K",
		"Sz",
		"Cs",
		"P",
		"Sz"
	],
	"eraAbbr": [
		"i. e.",
		"i. sz."
	],
	"field-day-relative+2": "holnapután",
	"field-day-relative+3": "három nap múlva",
	"dateFormatItem-yyyyMM": "yyyy.MM",
	"dateFormatItem-yyyyMMMM": "y. MMMM",
	"dateFormat-long": "y. MMMM d.",
	"timeFormat-medium": "H:mm:ss",
	"field-zone": "zóna",
	"dateFormatItem-Hm": "H:mm",
	"dateFormat-medium": "yyyy.MM.dd.",
	"dateFormatItem-Hms": "H:mm:ss",
	"quarters-standAlone-wide": [
		"I. negyedév",
		"II. negyedév",
		"III. negyedév",
		"IV. negyedév"
	],
	"field-year": "év",
	"field-week": "hét",
	"months-standAlone-wide": [
		"január",
		"február",
		"március",
		"április",
		"május",
		"június",
		"július",
		"augusztus",
		"szeptember",
		"október",
		"november",
		"december"
	],
	"dateFormatItem-MMMd": "MMM d.",
	"dateFormatItem-yyQ": "yy/Q",
	"timeFormat-long": "H:mm:ss z",
	"months-format-abbr": [
		"jan.",
		"febr.",
		"márc.",
		"ápr.",
		"máj.",
		"jún.",
		"júl.",
		"aug.",
		"szept.",
		"okt.",
		"nov.",
		"dec."
	],
	"timeFormat-short": "H:mm",
	"dateFormatItem-H": "H",
	"field-month": "hónap",
	"dateFormatItem-MMMMd": "MMMM d.",
	"quarters-format-abbr": [
		"N1",
		"N2",
		"N3",
		"N4"
	],
	"days-format-abbr": [
		"V",
		"H",
		"K",
		"Sze",
		"Cs",
		"P",
		"Szo"
	],
	"dateFormatItem-mmss": "mm:ss",
	"dateFormatItem-M": "L",
	"days-format-narrow": [
		"V",
		"H",
		"K",
		"Sz",
		"Cs",
		"P",
		"Sz"
	],
	"field-second": "másodperc",
	"field-day": "nap",
	"dateFormatItem-MEd": "M. d., E",
	"months-format-narrow": [
		"J",
		"F",
		"M",
		"Á",
		"M",
		"J",
		"J",
		"A",
		"Sz",
		"O",
		"N",
		"D"
	],
	"days-standAlone-abbr": [
		"V",
		"H",
		"K",
		"Sze",
		"Cs",
		"P",
		"Szo"
	],
	"dateFormat-short": "yyyy.MM.dd.",
	"dateFormatItem-yMMMEd": "y. MMM d., E",
	"dateFormat-full": "y. MMMM d., EEEE",
	"dateFormatItem-Md": "M. d.",
	"dateFormatItem-yMEd": "yyyy.MM.dd., E",
	"months-format-wide": [
		"január",
		"február",
		"március",
		"április",
		"május",
		"június",
		"július",
		"augusztus",
		"szeptember",
		"október",
		"november",
		"december"
	],
	"dateFormatItem-d": "d",
	"quarters-format-wide": [
		"I. negyedév",
		"II. negyedév",
		"III. negyedév",
		"IV. negyedév"
	],
	"days-format-wide": [
		"vasárnap",
		"hétfő",
		"kedd",
		"szerda",
		"csütörtök",
		"péntek",
		"szombat"
	],
	"eraNarrow": [
		"i. e.",
		"i. sz."
	]
}
//end v1.x content
);
},
'dojo/cldr/nls/hu/number':function(){
define(
"dojo/cldr/nls/hu/number", //begin v1.x content
{
	"group": " ",
	"percentSign": "%",
	"exponential": "E",
	"scientificFormat": "#E0",
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
'dojox/grid/enhanced/nls/hu/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/hu/EnhancedGrid", //begin v1.x content
({
	singleSort: "Egyszerű rendezés",
	nestedSort: "Beágyazott rendezés",
	ascending: "Növekvő",
	descending: "Csökkenő",
	sortingState: "${0} - ${1}",
	unsorted: "Ne rendezze ezt az oszlopot",
	indirectSelectionRadio: "${0} sor, egyetlen kijelölés, választógomb",
	indirectSelectionCheckBox: "${0} sor, több kijelölés, jelölőnégyzet",
	selectAll: "Összes kijelölése"
})
//end v1.x content
);


},
'dijit/_editor/nls/hu/commands':function(){
define(
"dijit/_editor/nls/hu/commands", //begin v1.x content
({
	'bold': 'Félkövér',
	'copy': 'Másolás',
	'cut': 'Kivágás',
	'delete': 'Törlés',
	'indent': 'Behúzás',
	'insertHorizontalRule': 'Vízszintes vonalzó',
	'insertOrderedList': 'Számozott lista',
	'insertUnorderedList': 'Felsorolásjeles lista',
	'italic': 'Dőlt',
	'justifyCenter': 'Középre igazítás',
	'justifyFull': 'Sorkizárás',
	'justifyLeft': 'Balra igazítás',
	'justifyRight': 'Jobbra igazítás',
	'outdent': 'Negatív behúzás',
	'paste': 'Beillesztés',
	'redo': 'Újra',
	'removeFormat': 'Formázás eltávolítása',
	'selectAll': 'Összes kijelölése',
	'strikethrough': 'Áthúzott',
	'subscript': 'Alsó index',
	'superscript': 'Felső index',
	'underline': 'Aláhúzott',
	'undo': 'Visszavonás',
	'unlink': 'Hivatkozás eltávolítása',
	'createLink': 'Hivatkozás létrehozása',
	'toggleDir': 'Irány váltókapcsoló',
	'insertImage': 'Kép beszúrása',
	'insertTable': 'Táblázat beszúrása/szerkesztése',
	'toggleTableBorder': 'Táblázatszegély ki-/bekapcsolása',
	'deleteTable': 'Táblázat törlése',
	'tableProp': 'Táblázat tulajdonságai',
	'htmlToggle': 'HTML forrás',
	'foreColor': 'Előtérszín',
	'hiliteColor': 'Háttérszín',
	'plainFormatBlock': 'Bekezdés stílusa',
	'formatBlock': 'Bekezdés stílusa',
	'fontSize': 'Betűméret',
	'fontName': 'Betűtípus',
	'tabIndent': 'Tab behúzás',
	"fullScreen": "Váltás teljes képernyőre",
	"viewSource": "HTML forrás megjelenítése",
	"print": "Nyomtatás",
	"newPage": "Új oldal",
	/* Error messages */
	'systemShortcut': 'A(z) "${0}" művelet a böngészőben csak billentyűparancs használatával érhető el. Használja a következőt: ${1}.'
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/hu/Pagination':function(){
define(
"dojox/grid/enhanced/nls/hu/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} / ${1} ${0}",
	"firstTip": "Első oldal",
	"lastTip": "Utolsó oldal",
	"nextTip": "Következő oldal",
	"prevTip": "Előző oldal",
	"itemTitle": "elemek",
	"singularItemTitle": "elem",
	"pageStepLabelTemplate": "${0}. oldal",
	"pageSizeLabelTemplate": "${0} elem oldalanként",
	"allItemsLabelTemplate": "Összes elem",
	"gotoButtonTitle": "Ugrás adott oldalra",
	"dialogTitle": "Ugrás adott oldalra",
	"dialogIndication": "Adja meg az oldalszámot",
	"pageCountIndication": " (${0} oldal)",
	"dialogConfirm": "Mehet",
	"dialogCancel": "Mégse",
	"all": "mind"
})
//end v1.x content
);


},
'dijit/form/nls/hu/validate':function(){
define(
"dijit/form/nls/hu/validate", //begin v1.x content
({
	invalidMessage: "A megadott érték érvénytelen.",
	missingMessage: "Meg kell adni egy értéket.",
	rangeMessage: "Az érték kívül van a megengedett tartományon."
})
//end v1.x content
);

},
'dojo/cldr/nls/hu/currency':function(){
define(
"dojo/cldr/nls/hu/currency", //begin v1.x content
{
	"HKD_displayName": "Hongkongi dollár",
	"CHF_displayName": "Svájci frank",
	"JPY_symbol": "¥",
	"CAD_displayName": "Kanadai dollár",
	"CNY_displayName": "Kínai jüan renminbi",
	"USD_symbol": "$",
	"AUD_displayName": "Ausztrál dollár",
	"JPY_displayName": "Japán jen",
	"USD_displayName": "USA dollár",
	"GBP_displayName": "Brit font sterling",
	"EUR_displayName": "Euro"
}
//end v1.x content
);
},
'dijit/form/nls/hu/ComboBox':function(){
define(
"dijit/form/nls/hu/ComboBox", //begin v1.x content
({
		previousMessage: "Előző menüpontok",
		nextMessage: "További menüpontok"
})
//end v1.x content
);

},
'dijit/nls/hu/loading':function(){
define(
"dijit/nls/hu/loading", //begin v1.x content
({
	loadingState: "Betöltés...",
	errorState: "Sajnálom, hiba történt"
})
//end v1.x content
);

}}});
define("dojo/nls/freenasdojo_hu", [], 1);
