diff --git src/util/util.h src/util/util.h
index 7a66846..5e63275 100644
--- src/util/util.h
+++ src/util/util.h
@@ -227,8 +227,6 @@ void sig_term(int sig);
 #include <signal.h>
 void BlockSignals(bool block, int signum);
 void (*CatchSignal(int signum,void (*handler)(int )))(int);
-void CatchChild(void);
-void CatchChildLeaveStatus(void);
 
 /* from memory.c */
 typedef int (void_destructor_fn_t)(void *);
@@ -542,5 +540,6 @@ char * sss_replace_space(TALLOC_CTX *mem_ctx,
 char * sss_reverse_replace_space(TALLOC_CTX *mem_ctx,
                                  const char *orig_name,
                                  const char replace_char);
+#include "util/sss_bsd_errno.h"
 
 #endif /* __SSSD_UTIL_H__ */
