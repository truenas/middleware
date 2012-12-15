#include <sys/types.h>
#include <sys/fcntl.h>
#include <sys/param.h>
#include <sys/sysctl.h>
#include <err.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <paths.h>

#define MAX_SIZE 9012

int main(int argc, char **argv)
{
    // Setup our vars
    char *progdir = NULL;
    char *progtarget = NULL;
    char newpath[MAX_SIZE];
    char newlibdir[MAX_SIZE];
    char newtarget[MAX_SIZE];

    // Setup working variables
    char bfile[PATH_MAX];
    char tfilepath[PATH_MAX];
    FILE *tfile; 
    char *optline;
    char *bufptr;
    char buf[1024];
    char cmpstr[1024];

    if ( strlen(argv[0]) > PATH_MAX ) {
       exit(2);
    }

    // Lets use sysctl to figure out where we are
    int mib[4];
    mib[0] = CTL_KERN;
    mib[1] = KERN_PROC;
    mib[2] = KERN_PROC_PATHNAME;
    mib[3] = -1;
    char mypath[1024];
    size_t cb = sizeof(mypath);
    sysctl(mib, 4, mypath, &cb, NULL, 0);

    if ( mypath[0] == 0 )
      strcpy(mypath, argv[0]);
    
    // Figure out where we are
    if (realpath(mypath, bfile) == NULL) {
       perror("Could not determine realpath...");
       return -1;
    }

    // Set the target file path
    strcpy(tfilepath, bfile);
    strcat(tfilepath, ".pbiopt");

    // Open target file
    tfile = fopen(tfilepath, "r");
    if ( tfile == NULL ) {
       printf("Missing pbi options file: %s\n", tfilepath);
       return -1;
    }

    // Read in .pbiopt file
    while ( (optline = fgets(buf, sizeof(buf), tfile)) != NULL ) {
       strcpy(cmpstr, "PROGDIR:"); 
       if ( ! strncmp(cmpstr, buf, strlen(cmpstr))) {
          bufptr = strdup(buf);
          progdir = strsep(&bufptr, " ");
          progdir = strsep(&bufptr, " ");
       }

       strcpy(cmpstr, "TARGET:"); 
       if ( ! strncmp(cmpstr, buf, strlen(cmpstr))) {
          bufptr = strdup(buf);
          progtarget = strsep(&bufptr, " ");
          progtarget = strsep(&bufptr, " ");
       }
    
    }
    fclose(tfile);

    if ( progdir == NULL ) {
       printf("Missing PROGDIR:");
       return -1;
    }
    if ( progtarget == NULL ) {
       printf("Missing TARGET:");
       return -1;
    }


    // Now check for .ldhints file
    strcpy(tfilepath, bfile);
    strcat(tfilepath, ".ldhints");

    // Open ldhints file
    tfile = fopen(tfilepath, "r");
    if ( tfile != NULL ) {
      if( (optline = fgets(buf, sizeof(buf), tfile)) != NULL ) {
         if ( (strlen(buf) + strlen(progdir) + 10) > MAX_SIZE ) {
           printf("Error: ldhints overflow!");
           exit(2);
         }
         strncpy(newlibdir, buf, (strlen(buf) -1));
         strcat(newlibdir, ":");  
      }
      fclose(tfile);
    }

    // Build the LDPATH
    strncat(newlibdir, progdir, (strlen(progdir) -1 ));
    strcat(newlibdir, "/lib");  

    // Sanity check newpath size before allocating
    if ( MAX_SIZE < ((strlen(progdir) + 10) * 3) + strlen(getenv("PATH")) ) {
       printf("PATH size overflow...");
       exit(2);
    }

    // Build the PATH
    strncpy(newpath, progdir, (strlen(progdir) -1 ));
    strcat(newpath, "/bin:");
    strncat(newpath, progdir, (strlen(progdir) -1 ));
    strcat(newpath, "/sbin:");
    strncat(newpath, progdir, (strlen(progdir) -1 ));
    strcat(newpath, "/libexec:");
    strcat(newpath, getenv("PATH"));

    // Set environment vars
    setenv("PATH", newpath, 1);
    setenv("LD_LIBRARY_PATH", newlibdir, 1);
    setenv("LD_32_LIBRARY_PATH", newlibdir, 1);

    // Set the target
    strncpy(newtarget, progdir, strlen(progdir) -1 );
    strcat(newtarget, "/");
    strncat(newtarget, progtarget, strlen(progtarget) -1 );

    // Enable for debug
    //printf( "PATH: %s\n", newpath);
    //printf( "LDPATH: %s\n", newlibdir);
    //printf( "Running: %s \n", newtarget);
    //return system(newtarget);
    return execv(newtarget, argv);
}
