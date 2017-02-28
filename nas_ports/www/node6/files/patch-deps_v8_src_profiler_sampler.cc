--- deps/v8/src/profiler/sampler.cc.orig	2016-10-19 22:02:04 UTC
+++ deps/v8/src/profiler/sampler.cc
@@ -534,9 +534,9 @@ void SignalHandler::HandleProfilerSignal
   state.sp = reinterpret_cast<Address>(mcontext.mc_rsp);
   state.fp = reinterpret_cast<Address>(mcontext.mc_rbp);
 #elif V8_HOST_ARCH_ARM
-  state.pc = reinterpret_cast<Address>(mcontext.mc_r15);
-  state.sp = reinterpret_cast<Address>(mcontext.mc_r13);
-  state.fp = reinterpret_cast<Address>(mcontext.mc_r11);
+  state.pc = reinterpret_cast<Address>(mcontext.__gregs[_REG_PC]);
+  state.sp = reinterpret_cast<Address>(mcontext.__gregs[_REG_SP]);
+  state.fp = reinterpret_cast<Address>(mcontext.__gregs[_REG_FP]);
 #endif  // V8_HOST_ARCH_*
 #elif V8_OS_NETBSD
 #if V8_HOST_ARCH_IA32
