require({cache:{
'dojox/form/nls/ca/CheckedMultiSelect':function(){
define(
"dojox/form/nls/ca/CheckedMultiSelect", ({
	invalidMessage: "Cal seleccionar, com a mínim, un element.",
	multiSelectLabelText: "{num} element(s) seleccionat(s)"
})
);

},
'dijit/nls/ca/common':function(){
define(
"dijit/nls/ca/common", //begin v1.x content
({
	buttonOk: "D'acord",
	buttonCancel: "Cancel·la",
	buttonSave: "Desa",
	itemClose: "Tanca"
})

//end v1.x content
);

},
'dojox/grid/enhanced/nls/ca/Filter':function(){
define(
"dojox/grid/enhanced/nls/ca/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "Netejar el filtre",
	"filterDefDialogTitle": "Filtre",
	"ruleTitleTemplate": "Regla ${0}",
	
	"conditionEqual": "igual que",
	"conditionNotEqual": "no és igual que",
	"conditionLess": "és menys que",
	"conditionLessEqual": "és menys o igual que",
	"conditionLarger": "és més que",
	"conditionLargerEqual": "és més o igual que",
	"conditionContains": "conté",
	"conditionIs": "és",
	"conditionStartsWith": "comença per",
	"conditionEndWith": "acaba per",
	"conditionNotContain": "no conté",
	"conditionIsNot": "no és",
	"conditionNotStartWith": "no comença per",
	"conditionNotEndWith": "no acaba per",
	"conditionBefore": "abans",
	"conditionAfter": "després",
	"conditionRange": "interval",
	"conditionIsEmpty": "és buida",
	
	"all": "tot",
	"any": "qualsevol",
	"relationAll": "totes les regles",
	"waiRelAll": "Fes coincidir totes les regles següents:",
	"relationAny": "qualsevol regla",
	"waiRelAny": "Fes coincidir qualsevol de les regles següents:",
	"relationMsgFront": "Coincidència",
	"relationMsgTail": "",
	"and": "i",
	"or": "o",
	
	"addRuleButton": "Afegeix regla",
	"waiAddRuleButton": "Afegeix una regla nova",
	"removeRuleButton": "Elimina regla",
	"waiRemoveRuleButtonTemplate": "Elimina la regla ${0}",
	
	"cancelButton": "Cancel·la",
	"waiCancelButton": "Cancel·la aquest diàleg",
	"clearButton": "Esborra",
	"waiClearButton": "Neteja el filtre",
	"filterButton": "Filtre",
	"waiFilterButton": "Envia el filtre",
	
	"columnSelectLabel": "Columna",
	"waiColumnSelectTemplate": "Columna per a la regla ${0}",
	"conditionSelectLabel": "Condició",
	"waiConditionSelectTemplate": "Condició per a la regla ${0}",
	"valueBoxLabel": "Valor",
	"waiValueBoxTemplate": "Especifiqueu el valor de filtre per a la regla ${0}",
	
	"rangeTo": "a",
	"rangeTemplate": "de ${0} a ${1}",
	
	"statusTipHeaderColumn": "Columna",
	"statusTipHeaderCondition": "Regles",
	"statusTipTitle": "Barra de filtre",
	"statusTipMsg": "Feu clic aquí a la barra de filtre per filtrar els valors a ${0}.",
	"anycolumn": "qualsevol columna",
	"statusTipTitleNoFilter": "Barra de filtre",
	"statusTipTitleHasFilter": "Filtre",
	"statusTipRelAny": "Coincideix amb qualsevol regla.",
	"statusTipRelAll": "Coincideix amb totes les regles.",
	
	"defaultItemsName": "elements",
	"filterBarMsgHasFilterTemplate": "Es mostren ${0} de ${1} ${2}.",
	"filterBarMsgNoFilterTemplate": "No s'ha aplicat cap filtre",
	
	"filterBarDefButton": "Defineix filtre",
	"waiFilterBarDefButton": "Filtra la taula",
	"a11yFilterBarDefButton": "Filtre...",
	"filterBarClearButton": "Netejar filtre",
	"waiFilterBarClearButton": "Neteja el filtre",
	"closeFilterBarBtn": "Tancar la barra de filtre",
	
	"clearFilterMsg": "Això eliminarà el filtre i mostrarà tots els registres disponibles.",
	"anyColumnOption": "Qualsevol columna",
	
	"trueLabel": "Cert",
	"falseLabel": "Fals"
})
//end v1.x content
);

},
'dojo/cldr/nls/ca/gregorian':function(){
define(
"dojo/cldr/nls/ca/gregorian", //begin v1.x content
{
	"months-format-narrow": [
		"g",
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
	"field-weekday": "dia de la setmana",
	"dateFormatItem-yQQQ": "QQQ y",
	"dateFormatItem-yMEd": "E d/M/yyyy",
	"dateFormatItem-MMMEd": "E d MMM",
	"eraNarrow": [
		"aC",
		"dC"
	],
	"dateFormat-long": "d MMMM 'de' y",
	"months-format-wide": [
		"de gener",
		"de febrer",
		"de març",
		"d’abril",
		"de maig",
		"de juny",
		"de juliol",
		"d’agost",
		"de setembre",
		"d’octubre",
		"de novembre",
		"de desembre"
	],
	"dateFormatItem-EEEd": "EEE d",
	"dayPeriods-format-wide-pm": "p.m.",
	"dateFormat-full": "EEEE d MMMM 'de' y",
	"dateFormatItem-Md": "d/M",
	"field-era": "era",
	"dateFormatItem-yM": "M/yyyy",
	"months-standAlone-wide": [
		"gener",
		"febrer",
		"març",
		"abril",
		"maig",
		"juny",
		"juliol",
		"agost",
		"setembre",
		"octubre",
		"novembre",
		"desembre"
	],
	"timeFormat-short": "H:mm",
	"quarters-format-wide": [
		"1r trimestre",
		"2n trimestre",
		"3r trimestre",
		"4t trimestre"
	],
	"timeFormat-long": "H:mm:ss z",
	"field-year": "any",
	"dateFormatItem-yMMM": "LLL y",
	"dateFormatItem-yQ": "Q yyyy",
	"field-hour": "hora",
	"months-format-abbr": [
		"de gen.",
		"de febr.",
		"de març",
		"d’abr.",
		"de maig",
		"de juny",
		"de jul.",
		"d’ag.",
		"de set.",
		"d’oct.",
		"de nov.",
		"de des."
	],
	"dateFormatItem-yyQ": "Q yy",
	"timeFormat-full": "H:mm:ss zzzz",
	"field-day-relative+0": "avui",
	"field-day-relative+1": "demà",
	"field-day-relative+2": "demà passat",
	"dateFormatItem-H": "H",
	"field-day-relative+3": "d'aquí a tres dies",
	"months-standAlone-abbr": [
		"gen.",
		"febr.",
		"març",
		"abr.",
		"maig",
		"juny",
		"jul.",
		"ag.",
		"set.",
		"oct.",
		"nov.",
		"des."
	],
	"quarters-format-abbr": [
		"1T",
		"2T",
		"3T",
		"4T"
	],
	"quarters-standAlone-wide": [
		"1r trimestre",
		"2n trimestre",
		"3r trimestre",
		"4t trimestre"
	],
	"dateFormatItem-M": "L",
	"days-standAlone-wide": [
		"diumenge",
		"dilluns",
		"dimarts",
		"dimecres",
		"dijous",
		"divendres",
		"dissabte"
	],
	"dateFormatItem-MMMMd": "d MMMM",
	"timeFormat-medium": "H:mm:ss",
	"dateFormatItem-Hm": "H:mm",
	"quarters-standAlone-abbr": [
		"1T",
		"2T",
		"3T",
		"4T"
	],
	"eraAbbr": [
		"aC",
		"dC"
	],
	"field-minute": "minut",
	"field-dayperiod": "a.m./p.m.",
	"days-standAlone-abbr": [
		"dg",
		"dl",
		"dt",
		"dc",
		"dj",
		"dv",
		"ds"
	],
	"dateFormatItem-d": "d",
	"dateFormatItem-ms": "mm:ss",
	"field-day-relative+-1": "ahir",
	"field-day-relative+-2": "abans d'ahir",
	"field-day-relative+-3": "fa tres dies",
	"dateFormatItem-MMMd": "d MMM",
	"dateFormatItem-MEd": "E d/M",
	"dateFormatItem-yMMMM": "LLLL 'del' y",
	"field-day": "dia",
	"days-format-wide": [
		"diumenge",
		"dilluns",
		"dimarts",
		"dimecres",
		"dijous",
		"divendres",
		"dissabte"
	],
	"field-zone": "zona",
	"dateFormatItem-yyyyMM": "MM/yyyy",
	"dateFormatItem-y": "y",
	"months-standAlone-narrow": [
		"g",
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
	"dateFormatItem-hm": "h:mm a",
	"days-format-abbr": [
		"dg.",
		"dl.",
		"dt.",
		"dc.",
		"dj.",
		"dv.",
		"ds."
	],
	"eraNames": [
		"aC",
		"dC"
	],
	"days-format-narrow": [
		"g",
		"l",
		"t",
		"c",
		"j",
		"v",
		"s"
	],
	"field-month": "mes",
	"days-standAlone-narrow": [
		"g",
		"l",
		"t",
		"c",
		"j",
		"v",
		"s"
	],
	"dateFormatItem-MMM": "LLL",
	"dayPeriods-format-wide-am": "a.m.",
	"dateFormatItem-MMMMEd": "E d MMMM",
	"dateFormat-short": "dd/MM/yy",
	"field-second": "segon",
	"dateFormatItem-yMMMEd": "EEE d MMM y",
	"field-week": "setmana",
	"dateFormat-medium": "dd/MM/yyyy",
	"dateFormatItem-mmss": "mm:ss",
	"dateFormatItem-Hms": "H:mm:ss",
	"dateFormatItem-hms": "h:mm:ss a"
}
//end v1.x content
);
},
'dojo/cldr/nls/ca/number':function(){
define(
"dojo/cldr/nls/ca/number", //begin v1.x content
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
	"currencyFormat": "#,##0.00 ¤",
	"plusSign": "+"
}
//end v1.x content
);
},
'dojox/grid/enhanced/nls/ca/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/ca/EnhancedGrid", //begin v1.x content
({
	singleSort: "Ordre únic",
	nestedSort: "Ordre imbricat",
	ascending: "Ascendent",
	descending: "Descendent",
	sortingState: "${0} - ${1}",
	unsorted: "No ordenis aquesta finestra",
	indirectSelectionRadio: "Fila ${0}, selecció única, quadre d'opció",
	indirectSelectionCheckBox: "Fila ${0}, selecció múltiple, quadre de selecció",
	selectAll: "Seleccionar-ho tot"
})
//end v1.x content
);


},
'dijit/_editor/nls/ca/commands':function(){
define(
"dijit/_editor/nls/ca/commands", //begin v1.x content
({
	'bold': 'Negreta',
	'copy': 'Copia',
	'cut': 'Retalla',
	'delete': 'Suprimeix',
	'indent': 'Sagnat',
	'insertHorizontalRule': 'Regla horitzontal',
	'insertOrderedList': 'Llista numerada',
	'insertUnorderedList': 'Llista de vinyetes',
	'italic': 'Cursiva',
	'justifyCenter': 'Centra',
	'justifyFull': 'Justifica',
	'justifyLeft': 'Alinea a l\'esquerra',
	'justifyRight': 'Alinea a la dreta',
	'outdent': 'Sagna a l\'esquerra',
	'paste': 'Enganxa',
	'redo': 'Refés',
	'removeFormat': 'Elimina el format',
	'selectAll': 'Selecciona-ho tot',
	'strikethrough': 'Ratllat',
	'subscript': 'Subíndex',
	'superscript': 'Superíndex',
	'underline': 'Subratllat',
	'undo': 'Desfés',
	'unlink': 'Elimina l\'enllaç',
	'createLink': 'Crea un enllaç',
	'toggleDir': 'Inverteix la direcció',
	'insertImage': 'Insereix imatge',
	'insertTable': 'Insereix/edita la taula',
	'toggleTableBorder': 'Inverteix els contorns de taula',
	'deleteTable': 'Suprimeix la taula',
	'tableProp': 'Propietat de taula',
	'htmlToggle': 'Font HTML',
	'foreColor': 'Color de primer pla',
	'hiliteColor': 'Color de fons',
	'plainFormatBlock': 'Estil de paràgraf',
	'formatBlock': 'Estil de paràgraf',
	'fontSize': 'Cos de la lletra',
	'fontName': 'Nom del tipus de lletra',
	'tabIndent': 'Sagnat',
	"fullScreen": "Commuta pantalla completa",
	"viewSource": "Visualitza font HTML",
	"print": "Imprimeix",
	"newPage": "Pàgina nova",
	/* Error messages */
	'systemShortcut': 'L\'acció "${0}" és l\'única disponible al navegador utilitzant una drecera del teclat. Utilitzeu ${1}.',
	'ctrlKey':'control+${0}'
})
//end v1.x content
);

},
'dojox/grid/enhanced/nls/ca/Pagination':function(){
define(
"dojox/grid/enhanced/nls/ca/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} de ${1} ${0}",
	"firstTip": "Primera pàgina",
	"lastTip": "Darrera pàgina",
	"nextTip": "Pàgina següent",
	"prevTip": "Pàgina anterior",
	"itemTitle": "elements",
	"singularItemTitle": "element",
	"pageStepLabelTemplate": "Pàgina ${0}",
	"pageSizeLabelTemplate": "${0} elements per pàgina",
	"allItemsLabelTemplate": "Tots els elements",
	"gotoButtonTitle": "Vés a una pàgina específica",
	"dialogTitle": "Vés a pàgina",
	"dialogIndication": "Especifiqueu el número de pàgina",
	"pageCountIndication": " (${0} pàgines)",
	"dialogConfirm": "Vés-hi",
	"dialogCancel": "Cancel·la",
	"all": "tot"
})
//end v1.x content
);

},
'dijit/form/nls/ca/validate':function(){
define(
"dijit/form/nls/ca/validate", //begin v1.x content
({
	invalidMessage: "El valor introduït no és vàlid",
	missingMessage: "Aquest valor és necessari",
	rangeMessage: "Aquest valor és fora de l'interval"
})

//end v1.x content
);

},
'dojo/cldr/nls/ca/currency':function(){
define(
"dojo/cldr/nls/ca/currency", //begin v1.x content
{
	"HKD_displayName": "dòlar de Hong Kong",
	"CHF_displayName": "franc suís",
	"CAD_displayName": "dòlar canadenc",
	"CNY_displayName": "iuan renmimbi xinès",
	"AUD_displayName": "dòlar australià",
	"JPY_displayName": "ien japonès",
	"USD_displayName": "dòlar dels Estats Units",
	"GBP_displayName": "lliura esterlina britànica",
	"EUR_displayName": "euro"
}
//end v1.x content
);
},
'dijit/form/nls/ca/ComboBox':function(){
define(
"dijit/form/nls/ca/ComboBox", //begin v1.x content
({
		previousMessage: "Opcions anteriors",
		nextMessage: "Més opcions"
})

//end v1.x content
);

},
'dijit/nls/ca/loading':function(){
define(
"dijit/nls/ca/loading", //begin v1.x content
({
	loadingState: "S'està carregant...",
	errorState: "Ens sap greu. S'ha produït un error."
})

//end v1.x content
);

}}});
define("dojo/nls/freenasdojo_ca", [], 1);
