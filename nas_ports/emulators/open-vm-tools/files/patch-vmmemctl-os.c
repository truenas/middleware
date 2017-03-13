--- modules/freebsd/vmmemctl/os.c.orig	2013-09-23 08:51:10.000000000 -0700
+++ modules/freebsd/vmmemctl/os.c	2017-02-20 21:19:02.000000000 -0800
@@ -37,9 +37,11 @@
 #include <sys/param.h>
 #include <sys/systm.h>
 #include <sys/kernel.h>
+#include <sys/lock.h>
 #include <sys/malloc.h>
 #include <sys/module.h>
 #include <sys/conf.h>
+#include <sys/rwlock.h>
 #include <sys/sysctl.h>
 
 #include <vm/vm.h>
@@ -223,7 +225,11 @@
 unsigned long
 OS_ReservedPageGetLimit(void)
 {
+#if __FreeBSD_version < 1100015
    return cnt.v_page_count;
+#else
+   return vm_cnt.v_page_count;
+#endif
 }
 
 
@@ -295,7 +301,13 @@
 Mapping
 OS_MapPageHandle(PageHandle handle)     // IN
 {
+
+#if __FreeBSD_version >= 1000042
+   vm_offset_t res = kva_alloc(PAGE_SIZE);
+#else
    vm_offset_t res = kmem_alloc_nofault(kernel_map, PAGE_SIZE);
+#endif
+
    vm_page_t page = (vm_page_t)handle;
 
    if (!res) {
@@ -352,7 +364,11 @@
 OS_UnmapPage(Mapping mapping)           // IN
 {
    pmap_qremove((vm_offset_t)mapping, 1);
+#if __FreeBSD_version >= 1000042
+   kva_free((vm_offset_t)mapping, PAGE_SIZE);
+#else
    kmem_free(kernel_map, (vm_offset_t)mapping, PAGE_SIZE);
+#endif
 }
 
 
@@ -360,7 +376,11 @@
 os_pmap_alloc(os_pmap *p) // IN
 {
    /* number of pages (div. 8) */
+#if __FreeBSD_version < 1100015
    p->size = (cnt.v_page_count + 7) / 8;
+#else
+   p->size = (vm_cnt.v_page_count + 7) / 8;
+#endif
 
    /*
     * expand to nearest word boundary 
@@ -369,14 +389,23 @@
    p->size = (p->size + sizeof(unsigned long) - 1) & 
                          ~(sizeof(unsigned long) - 1);
 
+#if __FreeBSD_version >= 1000042
+   p->bitmap = (unsigned long *)kmem_malloc(kernel_arena, p->size,
+                         M_WAITOK | M_ZERO);
+#else
    p->bitmap = (unsigned long *)kmem_alloc(kernel_map, p->size);
+#endif
 }
 
 
 static void
 os_pmap_free(os_pmap *p) // IN
 {
+#if __FreeBSD_version >= 1000042
+   kva_free((vm_offset_t)p->bitmap, p->size);
+#else
    kmem_free(kernel_map, (vm_offset_t)p->bitmap, p->size);
+#endif
    p->size = 0;
    p->bitmap = NULL;
 }
@@ -449,12 +478,31 @@
    os_state *state = &global_state;
    os_pmap *pmap = &state->pmap;
 
-   if ( !vm_page_lookup(state->vmobject, page->pindex) ) {
-      return;
-   }
 
-   os_pmap_putindex(pmap, page->pindex);
-   vm_page_free(page);
+#if __FreeBSD_version > 1000029
+   VM_OBJECT_WLOCK(state->vmobject);
+#else
+   VM_OBJECT_LOCK(state->vmobject);
+#endif
+   if ( vm_page_lookup(state->vmobject, page->pindex) ) {
+   	os_pmap_putindex(pmap, page->pindex);
+#if __FreeBSD_version >= 900000
+	vm_page_lock(page);
+#else
+	vm_page_lock_queues();
+#endif
+   	vm_page_free(page);
+#if __FreeBSD_version >= 900000
+	vm_page_unlock(page);
+#else
+	vm_page_unlock_queues();
+#endif
+   }
+#if __FreeBSD_version > 1000029
+   VM_OBJECT_WUNLOCK(state->vmobject);
+#else
+   VM_OBJECT_UNLOCK(state->vmobject);
+#endif
 }
 
 
@@ -466,8 +514,19 @@
    os_state *state = &global_state;
    os_pmap *pmap = &state->pmap;
 
+#if __FreeBSD_version > 1000029
+   VM_OBJECT_WLOCK(state->vmobject);
+#else
+   VM_OBJECT_LOCK(state->vmobject);
+#endif
+
    pindex = os_pmap_getindex(pmap);
    if (pindex == (vm_pindex_t)-1) {
+#if __FreeBSD_version > 1000029
+      VM_OBJECT_WUNLOCK(state->vmobject);
+#else
+      VM_OBJECT_UNLOCK(state->vmobject);
+#endif
       return NULL;
    }
 
@@ -488,6 +547,11 @@
    if (!page) {
       os_pmap_putindex(pmap, pindex);
    }
+#if __FreeBSD_version > 1000029
+   VM_OBJECT_WUNLOCK(state->vmobject);
+#else
+   VM_OBJECT_UNLOCK(state->vmobject);
+#endif
 
    return page;
 }
@@ -824,7 +888,7 @@
 static void
 vmmemctl_init_sysctl(void)
 {
-   oid =  sysctl_add_oid(NULL, SYSCTL_STATIC_CHILDREN(_vm), OID_AUTO,
+   oid =  SYSCTL_ADD_OID(NULL, SYSCTL_STATIC_CHILDREN(_vm), OID_AUTO,
                          BALLOON_NAME, CTLTYPE_STRING | CTLFLAG_RD,
                          0, 0, vmmemctl_sysctl, "A",
                          BALLOON_NAME_VERBOSE);
