--- snmplib/snmp_api.c.orig	2014-12-08 20:23:22 UTC
+++ snmplib/snmp_api.c
@@ -4350,10 +4350,9 @@ snmp_pdu_parse(netsnmp_pdu *pdu, u_char 
     u_char          type;
     u_char          msg_type;
     u_char         *var_val;
-    int             badtype = 0;
     size_t          len;
     size_t          four;
-    netsnmp_variable_list *vp = NULL;
+    netsnmp_variable_list *vp = NULL, *vplast = NULL;
     oid             objid[MAX_OID_LEN];
     u_char         *p;
 
@@ -4493,38 +4492,24 @@ snmp_pdu_parse(netsnmp_pdu *pdu, u_char 
                               (ASN_SEQUENCE | ASN_CONSTRUCTOR),
                               "varbinds");
     if (data == NULL)
-        return -1;
+        goto fail;
 
     /*
      * get each varBind sequence 
      */
     while ((int) *length > 0) {
-        netsnmp_variable_list *vptemp;
-        vptemp = (netsnmp_variable_list *) malloc(sizeof(*vptemp));
-        if (NULL == vptemp) {
-            return -1;
-        }
-        if (NULL == vp) {
-            pdu->variables = vptemp;
-        } else {
-            vp->next_variable = vptemp;
-        }
-        vp = vptemp;
+	vp = SNMP_MALLOC_TYPEDEF(netsnmp_variable_list);
+	if (NULL == vp)
+	    goto fail;
 
-        vp->next_variable = NULL;
-        vp->val.string = NULL;
         vp->name_length = MAX_OID_LEN;
-        vp->name = NULL;
-        vp->index = 0;
-        vp->data = NULL;
-        vp->dataFreeHook = NULL;
         DEBUGDUMPSECTION("recv", "VarBind");
         data = snmp_parse_var_op(data, objid, &vp->name_length, &vp->type,
                                  &vp->val_len, &var_val, length);
         if (data == NULL)
-            return -1;
+            goto fail;
         if (snmp_set_var_objid(vp, objid, vp->name_length))
-            return -1;
+            goto fail;
 
         len = MAX_PACKET_LENGTH;
         DEBUGDUMPHEADER("recv", "Value");
@@ -4604,7 +4589,7 @@ snmp_pdu_parse(netsnmp_pdu *pdu, u_char 
                 vp->val.string = (u_char *) malloc(vp->val_len);
             }
             if (vp->val.string == NULL) {
-                return -1;
+                goto fail;
             }
             p = asn_parse_string(var_val, &len, &vp->type, vp->val.string,
                              &vp->val_len);
@@ -4619,7 +4604,7 @@ snmp_pdu_parse(netsnmp_pdu *pdu, u_char 
             vp->val_len *= sizeof(oid);
             vp->val.objid = (oid *) malloc(vp->val_len);
             if (vp->val.objid == NULL) {
-                return -1;
+                goto fail;
             }
             memmove(vp->val.objid, objid, vp->val_len);
             break;
@@ -4631,7 +4616,7 @@ snmp_pdu_parse(netsnmp_pdu *pdu, u_char 
         case ASN_BIT_STR:
             vp->val.bitstring = (u_char *) malloc(vp->val_len);
             if (vp->val.bitstring == NULL) {
-                return -1;
+                goto fail;
             }
             p = asn_parse_bitstring(var_val, &len, &vp->type,
                                 vp->val.bitstring, &vp->val_len);
@@ -4640,12 +4625,28 @@ snmp_pdu_parse(netsnmp_pdu *pdu, u_char 
             break;
         default:
             snmp_log(LOG_ERR, "bad type returned (%x)\n", vp->type);
-            badtype = -1;
+            goto fail;
             break;
         }
         DEBUGINDENTADD(-4);
+
+	if (NULL == vplast) {
+	    pdu->variables = vp;
+	} else {
+	    vplast->next_variable = vp;
+	}
+	vplast = vp;
+	vp = NULL;
     }
-    return badtype;
+    return 0;
+
+  fail:
+    DEBUGMSGTL(("recv", "error while parsing VarBindList\n"));
+    /** if we were parsing a var, remove it from the pdu and free it */
+    if (vp)
+	snmp_free_var(vp);
+
+     return -1;
 }
 
 /*
