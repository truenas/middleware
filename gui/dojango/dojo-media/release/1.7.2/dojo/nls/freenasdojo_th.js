require({cache:{
'dojox/form/nls/th/CheckedMultiSelect':function(){
define(
"dojox/form/nls/th/CheckedMultiSelect", ({
	invalidMessage: "อย่างน้อยหนึ่งรายการต้องถูกเลือก",
	multiSelectLabelText: "{num} รายการถูกเลือก"
})
);

},
'dijit/nls/th/common':function(){
define(
"dijit/nls/th/common", //begin v1.x content
({
	buttonOk: "ตกลง",
	buttonCancel: "ยกเลิก",
	buttonSave: "บันทึก",
	itemClose: "ปิด"
})

//end v1.x content
);

},
'dojox/grid/enhanced/nls/th/Filter':function(){
define(
"dojox/grid/enhanced/nls/th/Filter", //begin v1.x content
({
	"clearFilterDialogTitle": "ลบตัวกรอง",
	"filterDefDialogTitle": "ตัวกรอง",
	"ruleTitleTemplate": "กฏ ${0}",
	
	"conditionEqual": "เท่ากับ",
	"conditionNotEqual": "ไม่เท่ากับ",
	"conditionLess": "น้อยกว่า",
	"conditionLessEqual": "น้อยกว่าหรือเท่ากับ",
	"conditionLarger": "มากกว่า",
	"conditionLargerEqual": "มากกว่าหรือเท่ากับ",
	"conditionContains": "ประกอบด้วย",
	"conditionIs": "เป็น",
	"conditionStartsWith": "เริ่มต้นด้วย",
	"conditionEndWith": "ลงท้ายด้วย",
	"conditionNotContain": "ไม่ประกอบด้วย",
	"conditionIsNot": "ไม่",
	"conditionNotStartWith": "ไม่เริ่มต้นด้วย",
	"conditionNotEndWith": "ไม่ลงท้ายด้วย",
	"conditionBefore": "ก่อน",
	"conditionAfter": "หลัง",
	"conditionRange": "ช่วง",
	"conditionIsEmpty": "ว่างอยู่",
	
	"all": "ทั้งหมด",
	"any": "ใด",
	"relationAll": "กฏทั้งหมด",
	"waiRelAll": "ตรงกับกฏทั้งหมดต่อไปนี้:",
	"relationAny": "กฏใดๆ",
	"waiRelAny": "ตรงกับกฏใดๆต่อไปนี้:",
	"relationMsgFront": "ตรงกับ",
	"relationMsgTail": "",
	"and": "และ",
	"or": "หรือ",
	
	"addRuleButton": "เพิ่มกฏ",
	"waiAddRuleButton": "เพิ่มกฏใหม่",
	"removeRuleButton": "ลบกฏ",
	"waiRemoveRuleButtonTemplate": "ลบกฏ ${0}",
	
	"cancelButton": "ยกเลิก",
	"waiCancelButton": "ยกเลิกไดอะล็อกนี้",
	"clearButton": "ลบ",
	"waiClearButton": "ลบตัวกรอง",
	"filterButton": "ตัวกรอง",
	"waiFilterButton": "ส่งตัวกรอง",
	
	"columnSelectLabel": "คอลัมน์",
	"waiColumnSelectTemplate": "คอลัมน์สำหรับกฏ ${0}",
	"conditionSelectLabel": "เงื่อนไข",
	"waiConditionSelectTemplate": "เงื่อนไขสำหรับกฏ ${0}",
	"valueBoxLabel": "ค่า",
	"waiValueBoxTemplate": "ป้อนค่าให้กับตัวกรองสำหรับกฏ ${0}",
	
	"rangeTo": "ถึง",
	"rangeTemplate": "จาก ${0} ถึง ${1}",
	
	"statusTipHeaderColumn": "คอลัมน์",
	"statusTipHeaderCondition": "กฏ",
	"statusTipTitle": "แถบตัวกรอง",
	"statusTipMsg": "คลิกที่แถบตัวกรองที่นี่เพื่อกรองค่าใน ${0}",
	"anycolumn": "คอลัมน์ใดๆ",
	"statusTipTitleNoFilter": "แถบตัวกรอง",
	"statusTipTitleHasFilter": "ตัวกรอง",
	"statusTipRelAny": "ตรงกับกฏใดๆ",
	"statusTipRelAll": "ตรงกับทุกกฏ",
	
	"defaultItemsName": "ไอเท็ม",
	"filterBarMsgHasFilterTemplate": "${0} ของ ${1} ${2} จะถูกแสดง",
	"filterBarMsgNoFilterTemplate": "ไม่นำตัวกรองไปใช้",
	
	"filterBarDefButton": "กำหนดตัวกรอง",
	"waiFilterBarDefButton": "กรองตาราง",
	"a11yFilterBarDefButton": "ตัวกรอง...",
	"filterBarClearButton": "ลบตัวกรอง",
	"waiFilterBarClearButton": "ลบตัวกรอง",
	"closeFilterBarBtn": "ปิดแถบตัวกรอง",
	
	"clearFilterMsg": "ซึ่งจะลบตัวกรองออกและแสดงเร็กคอร์ดที่พร้อมใช้งานทั้งหมด",
	"anyColumnOption": "คอลัมน์ใดๆ",
	
	"trueLabel": "จริง",
	"falseLabel": "เท็จ"
})
//end v1.x content
);

},
'dojo/cldr/nls/th/gregorian':function(){
define(
"dojo/cldr/nls/th/gregorian", //begin v1.x content
{
	"months-format-narrow": [
		"ม.ค.",
		"ก.พ.",
		"มี.ค.",
		"เม.ย.",
		"พ.ค.",
		"มิ.ย.",
		"ก.ค.",
		"ส.ค.",
		"ก.ย.",
		"ต.ค.",
		"พ.ย.",
		"ธ.ค."
	],
	"field-weekday": "วันในสัปดาห์",
	"dateFormatItem-yQQQ": "QQQ y",
	"dateFormatItem-yMEd": "EEE d/M/yyyy",
	"dateFormatItem-MMMEd": "E d MMM",
	"eraNarrow": [
		"ก่อน ค.ศ.",
		"ค.ศ."
	],
	"dateFormat-long": "d MMMM y",
	"months-format-wide": [
		"มกราคม",
		"กุมภาพันธ์",
		"มีนาคม",
		"เมษายน",
		"พฤษภาคม",
		"มิถุนายน",
		"กรกฎาคม",
		"สิงหาคม",
		"กันยายน",
		"ตุลาคม",
		"พฤศจิกายน",
		"ธันวาคม"
	],
	"dateTimeFormat-medium": "{1}, {0}",
	"dateFormatItem-EEEd": "EEE d",
	"dayPeriods-format-wide-pm": "หลังเที่ยง",
	"dateFormat-full": "EEEEที่ d MMMM G y",
	"dateFormatItem-Md": "d/M",
	"field-era": "สมัย",
	"dateFormatItem-yM": "M/yyyy",
	"months-standAlone-wide": [
		"มกราคม",
		"กุมภาพันธ์",
		"มีนาคม",
		"เมษายน",
		"พฤษภาคม",
		"มิถุนายน",
		"กรกฎาคม",
		"สิงหาคม",
		"กันยายน",
		"ตุลาคม",
		"พฤศจิกายน",
		"ธันวาคม"
	],
	"timeFormat-short": "H:mm",
	"quarters-format-wide": [
		"ไตรมาส 1",
		"ไตรมาส 2",
		"ไตรมาส 3",
		"ไตรมาส 4"
	],
	"timeFormat-long": "H นาฬิกา m นาที ss วินาที z",
	"field-year": "ปี",
	"dateFormatItem-yMMM": "MMM y",
	"dateFormatItem-yQ": "Q yyyy",
	"dateFormatItem-yyyyMMMM": "MMMM y",
	"field-hour": "ชั่วโมง",
	"months-format-abbr": [
		"ม.ค.",
		"ก.พ.",
		"มี.ค.",
		"เม.ย.",
		"พ.ค.",
		"มิ.ย.",
		"ก.ค.",
		"ส.ค.",
		"ก.ย.",
		"ต.ค.",
		"พ.ย.",
		"ธ.ค."
	],
	"dateFormatItem-yyQ": "Q yy",
	"timeFormat-full": "H นาฬิกา m นาที ss วินาที zzzz",
	"field-day-relative+0": "วันนี้",
	"field-day-relative+1": "พรุ่งนี้",
	"field-day-relative+2": "มะรืนนี้",
	"dateFormatItem-H": "H",
	"field-day-relative+3": "สามวันต่อจากนี้",
	"months-standAlone-abbr": [
		"ม.ค.",
		"ก.พ.",
		"มี.ค.",
		"เม.ย.",
		"พ.ค.",
		"มิ.ย.",
		"ก.ค.",
		"ส.ค.",
		"ก.ย.",
		"ต.ค.",
		"พ.ย.",
		"ธ.ค."
	],
	"quarters-format-abbr": [
		"Q1",
		"Q2",
		"Q3",
		"Q4"
	],
	"quarters-standAlone-wide": [
		"ไตรมาส 1",
		"ไตรมาส 2",
		"ไตรมาส 3",
		"ไตรมาส 4"
	],
	"dateFormatItem-M": "L",
	"days-standAlone-wide": [
		"วันอาทิตย์",
		"วันจันทร์",
		"วันอังคาร",
		"วันพุธ",
		"วันพฤหัสบดี",
		"วันศุกร์",
		"วันเสาร์"
	],
	"dateFormatItem-MMMMd": "d MMMM",
	"timeFormat-medium": "H:mm:ss",
	"dateFormatItem-Hm": "H:mm",
	"eraAbbr": [
		"ปีก่อน ค.ศ.",
		"ค.ศ."
	],
	"field-minute": "นาที",
	"field-dayperiod": "ช่วงวัน",
	"days-standAlone-abbr": [
		"อา.",
		"จ.",
		"อ.",
		"พ.",
		"พฤ.",
		"ศ.",
		"ส."
	],
	"dateFormatItem-d": "d",
	"dateFormatItem-ms": "mm:ss",
	"field-day-relative+-1": "เมื่อวาน",
	"dateTimeFormat-long": "{1}, {0}",
	"field-day-relative+-2": "เมื่อวานซืน",
	"field-day-relative+-3": "สามวันก่อน",
	"dateFormatItem-MMMd": "d MMM",
	"dateFormatItem-MEd": "E, d/M",
	"dateTimeFormat-full": "{1}, {0}",
	"dateFormatItem-yMMMM": "MMMM y",
	"field-day": "วัน",
	"days-format-wide": [
		"วันอาทิตย์",
		"วันจันทร์",
		"วันอังคาร",
		"วันพุธ",
		"วันพฤหัสบดี",
		"วันศุกร์",
		"วันเสาร์"
	],
	"field-zone": "เขต",
	"dateFormatItem-y": "y",
	"months-standAlone-narrow": [
		"ม.ค.",
		"ก.พ.",
		"มี.ค.",
		"เม.ย.",
		"พ.ค.",
		"มิ.ย.",
		"ก.ค.",
		"ส.ค.",
		"ก.ย.",
		"ต.ค.",
		"พ.ย.",
		"ธ.ค."
	],
	"days-format-abbr": [
		"อา.",
		"จ.",
		"อ.",
		"พ.",
		"พฤ.",
		"ศ.",
		"ส."
	],
	"eraNames": [
		"ปีก่อนคริสต์ศักราช",
		"คริสต์ศักราช"
	],
	"days-format-narrow": [
		"อ",
		"จ",
		"อ",
		"พ",
		"พ",
		"ศ",
		"ส"
	],
	"field-month": "เดือน",
	"days-standAlone-narrow": [
		"อ",
		"จ",
		"อ",
		"พ",
		"พ",
		"ศ",
		"ส"
	],
	"dateFormatItem-MMM": "LLL",
	"dayPeriods-format-wide-am": "ก่อนเที่ยง",
	"dateFormatItem-MMMMEd": "E d MMMM",
	"dateFormat-short": "d/M/yyyy",
	"field-second": "วินาที",
	"dateFormatItem-yMMMEd": "EEE d MMM y",
	"field-week": "สัปดาห์",
	"dateFormat-medium": "d MMM y",
	"dateFormatItem-yyyyM": "M/yyyy",
	"dateFormatItem-mmss": "mm:ss",
	"dateTimeFormat-short": "{1}, {0}",
	"dateFormatItem-Hms": "H:mm:ss"
}
//end v1.x content
);
},
'dojo/cldr/nls/th/number':function(){
define(
"dojo/cldr/nls/th/number", //begin v1.x content
{
	"group": ",",
	"percentSign": "%",
	"exponential": "E",
	"scientificFormat": "#E0",
	"percentFormat": "#,##0%",
	"list": ";",
	"infinity": "∞",
	"patternDigit": "#",
	"minusSign": "-",
	"decimal": ".",
	"nan": "NaN",
	"nativeZeroDigit": "0",
	"perMille": "‰",
	"decimalFormat": "#,##0.###",
	"currencyFormat": "¤#,##0.00;¤-#,##0.00",
	"plusSign": "+"
}
//end v1.x content
);
},
'dojox/grid/enhanced/nls/th/EnhancedGrid':function(){
define(
"dojox/grid/enhanced/nls/th/EnhancedGrid", //begin v1.x content
({
	singleSort: "เรียงลำดับแบบเดี่ยว",
	nestedSort: "เรียงลำดับที่ซับซ้อน",
	ascending: "จากน้อยไปหามาก",
	descending: "จากมากไปหาน้อย",
	sortingState: "${0} - ${1}",
	unsorted: "ห้ามเรียงลำดับคอลัมน์นี้",
	indirectSelectionRadio: "แถว ${0}, การเลือกเดียว, กล่องวิทยุ",
	indirectSelectionCheckBox: "แถว ${0}, การเลือกจำนวนมาก, เช็กบ็อกซ์",
	selectAll: "เลือกทั้งหมด"
})
//end v1.x content
);


},
'dijit/_editor/nls/th/commands':function(){
define(
"dijit/_editor/nls/th/commands", //begin v1.x content
({
	'bold': 'ตัวหนา',
	'copy': 'คัดลอก',
	'cut': 'ตัด',
	'delete': 'ลบ',
	'indent': 'เพิ่มการเยื้อง',
	'insertHorizontalRule': 'ไม้บรรทัดแนวนอน',
	'insertOrderedList': 'ลำดับเลข',
	'insertUnorderedList': 'หัวข้อย่อย',
	'italic': 'ตัวเอียง',
	'justifyCenter': 'จัดกึ่งกลาง',
	'justifyFull': 'จัดชิดขอบ',
	'justifyLeft': 'จัดชิดซ้าย',
	'justifyRight': 'จัดชิดขวา',
	'outdent': 'ลดการเยื้อง',
	'paste': 'วาง',
	'redo': 'ทำซ้ำ',
	'removeFormat': 'ลบรูปแบบออก',
	'selectAll': 'เลือกทั้งหมด',
	'strikethrough': 'ขีดทับ',
	'subscript': 'ตัวห้อย',
	'superscript': 'ตัวยก',
	'underline': 'ขีดเส้นใต้',
	'undo': 'เลิกทำ',
	'unlink': 'ลบลิงก์ออก',
	'createLink': 'สร้างลิงก์',
	'toggleDir': 'สลับทิศทาง',
	'insertImage': 'แทรกอิมเมจ',
	'insertTable': 'แทรก/แก้ไขตาราง',
	'toggleTableBorder': 'สลับเส้นขอบตาราง',
	'deleteTable': 'ลบตาราง',
	'tableProp': 'คุณสมบัติตาราง',
	'htmlToggle': 'ซอร์ส HTML',
	'foreColor': 'สีพื้นหน้า',
	'hiliteColor': 'สีพื้นหลัง',
	'plainFormatBlock': 'ลักษณะย่อหน้า',
	'formatBlock': 'ลักษณะย่อหน้า',
	'fontSize': 'ขนาดฟอนต์',
	'fontName': 'ชื่อฟอนต์',
	'tabIndent': 'เยื้องแท็บ',
	"fullScreen": "สลับจอภาพแบบเต็ม",
	"viewSource": "ดูซอร์ส HTML",
	"print": "พิมพ์",
	"newPage": "หน้าใหม่",
	/* Error messages */
	'systemShortcut': 'การดำเนินการ"${0}" ใช้งานได้เฉพาะกับเบราว์เซอร์ของคุณโดยใช้แป้นพิมพ์ลัด ใช้ ${1}'
})

//end v1.x content
);

},
'dojox/grid/enhanced/nls/th/Pagination':function(){
define(
"dojox/grid/enhanced/nls/th/Pagination", //begin v1.x content
({
	"descTemplate": "${2} - ${3} จาก ${1} ${0}",
	"firstTip": "หน้าแรก",
	"lastTip": "หน้าสุดท้าย",
	"nextTip": "หน้าถัดไป",
	"prevTip": "หน้าก่อนหน้านี้",
	"itemTitle": "ไอเท็ม",
	"singularItemTitle": "ไอเท็ม",
	"pageStepLabelTemplate": "หน้า ${0}",
	"pageSizeLabelTemplate": "${0} ไอเท็มต่อหน้า",
	"allItemsLabelTemplate": "รายการ ทั้งหมด",
	"gotoButtonTitle": "ไปที่หน้าที่ระบุ",
	"dialogTitle": "ไปที่หน้า",
	"dialogIndication": "ระบุหมายเลขหน้า",
	"pageCountIndication": " (${0} หน้า)",
	"dialogConfirm": "ไปที่",
	"dialogCancel": "ยกเลิก",
	"all": "ทั้งหมด"
})
//end v1.x content
);

},
'dijit/form/nls/th/validate':function(){
define(
"dijit/form/nls/th/validate", //begin v1.x content
({
	invalidMessage: "ค่าที่ป้อนไม่ถูกต้อง",
	missingMessage: "จำเป็นต้องมีค่านี้",
	rangeMessage: "ค่านี้เกินช่วง"
})

//end v1.x content
);

},
'dojo/cldr/nls/th/currency':function(){
define(
"dojo/cldr/nls/th/currency", //begin v1.x content
{
	"HKD_displayName": "ดอลลาร์ฮ่องกง",
	"CHF_displayName": "ฟรังก์สวิส",
	"JPY_symbol": "¥",
	"CAD_displayName": "ดอลลาร์แคนาดา",
	"CNY_displayName": "หยวนเหรินหมินปี้ (สาธารณรัฐประชาชนจีน)",
	"AUD_displayName": "ดอลลาร์ออสเตรเลีย",
	"JPY_displayName": "เยนญี่ปุ่น",
	"USD_displayName": "ดอลลาร์สหรัฐ",
	"GBP_displayName": "ปอนด์สเตอร์ลิง (สหราชอาณาจักร)",
	"EUR_displayName": "ยูโร"
}
//end v1.x content
);
},
'dijit/form/nls/th/ComboBox':function(){
define(
"dijit/form/nls/th/ComboBox", //begin v1.x content
({
		previousMessage: "การเลือกก่อนหน้า",
		nextMessage: "การเลือกเพิ่มเติม"
})

//end v1.x content
);

},
'dijit/nls/th/loading':function(){
define(
"dijit/nls/th/loading", //begin v1.x content
({
	loadingState: "กำลังโหลด...",
	errorState: "ขออภัย เกิดข้อผิดพลาด"
})

//end v1.x content
);

}}});
define("dojo/nls/freenasdojo_th", [], 1);
