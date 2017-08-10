--- src/apps_plugin.c.orig	2017-07-18 22:52:41 UTC
+++ src/apps_plugin.c
@@ -1572,7 +1572,13 @@ static inline int read_pid_file_descript
                             break;
                         default:
                             /* print protocol number and socket address */
-                            sprintf(fdsname, "socket: other: %d %s %s", fds->kf_sock_protocol, fds->kf_sa_local.__ss_pad1, fds->kf_sa_local.__ss_pad2);
+                            sprintf(fdsname, "socket: other: %d %s %s", fds->kf_sock_protocol,
+                #if defined(__FreeBSD__) && (__FreeBSD_version >= 1200031)
+                            fds->kf_un.kf_sock.kf_sa_local.__ss_pad1, fds->kf_un.kf_sock.kf_sa_local.__ss_pad2
+                #else
+                            fds->kf_sa_local.__ss_pad1, fds->kf_sa_local.__ss_pad2
+                #endif
+                            );
                     }
                     break;
                 case KF_TYPE_PIPE:
