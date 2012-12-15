#############################################################################
# Makefile for building: /usr/local/bin/pbiwrapper
#############################################################################

####### Compiler, tools and options

CC            = gcc
CXX           = g++
DEFINES       = -DQT_NO_DEBUG -DQT_GUI_LIB -DQT_CORE_LIB -DQT_SHARED
CFLAGS        = -pipe -O2 -Wall -W $(DEFINES)
CXXFLAGS      = -pipe -O2 -Wall -W $(DEFINES)
INCPATH       = -I/usr/local/include -I. -I/usr/local/include
LINK          = gcc
LFLAGS        = -Wl,-O1
LIBS          = $(SUBLIBS)
AR            = ar cqs
RANLIB        = 
QMAKE         = /usr/local/bin/qmake-qt4
TAR           = tar -cf
COMPRESS      = gzip -9f
COPY          = cp -f
SED           = sed
COPY_FILE     = $(COPY)
COPY_DIR      = $(COPY) -R
STRIP         = 
INSTALL_FILE  = $(COPY_FILE)
INSTALL_DIR   = $(COPY_DIR)
INSTALL_PROGRAM = $(COPY_FILE)
DEL_FILE      = rm -f
SYMLINK       = ln -f -s
DEL_DIR       = rmdir
MOVE          = mv -f
CHK_DIR_EXISTS= test -d
MKDIR         = mkdir -p

####### Output directory

OBJECTS_DIR   = ./

####### Files

SOURCES       = main.c 
OBJECTS       = main.o
MAKE_TARGET   = .pbiwrapper
DESTDIR       = /usr/pbi/
TARGET        = .pbiwrapper

first: all
####### Implicit rules

.SUFFIXES: .o .c .cpp .cc .cxx .C

.cpp.o:
	$(CXX) -c $(CXXFLAGS) $(INCPATH) -o "$@" "$<"

.cc.o:
	$(CXX) -c $(CXXFLAGS) $(INCPATH) -o "$@" "$<"

.cxx.o:
	$(CXX) -c $(CXXFLAGS) $(INCPATH) -o "$@" "$<"

.C.o:
	$(CXX) -c $(CXXFLAGS) $(INCPATH) -o "$@" "$<"

.c.o:
	$(CC) -c $(CFLAGS) $(INCPATH) -o "$@" "$<"

####### Build rules

all: Makefile $(TARGET)

$(TARGET):  $(OBJECTS)  
	@$(CHK_DIR_EXISTS) /usr/pbi/ || $(MKDIR) /usr/pbi/
	$(LINK) $(LFLAGS) -o $(TARGET) $(OBJECTS) $(OBJCOMP) $(LIBS)

Makefile:

dist: 
	@$(CHK_DIR_EXISTS) .tmp/pbiwrapper || $(MKDIR) .tmp/pbiwrapper1.0.0 
	$(COPY_FILE) --parents $(SOURCES) $(DIST) .tmp/pbiwrapper1.0.0/ && $(COPY_FILE) --parents updatecheck.c .tmp/pbiwrapper1.0.0/ && (cd `dirname .tmp/pbiwrapper1.0.0` && $(TAR) pbiwrapper1.0.0.tar pbiwrapper1.0.0 && $(COMPRESS) pbiwrapper1.0.0.tar) && $(MOVE) `dirname .tmp/pbiwrapper1.0.0`/pbiwrapper1.0.0.tar.gz . && $(DEL_FILE) -r .tmp/pbiwrapper1.0.0


clean:compiler_clean 
	-$(DEL_FILE) $(OBJECTS)
	-$(DEL_FILE) *~ core *.core


####### Sub-libraries

distclean: clean
	-$(DEL_FILE) $(TARGET) 
	-$(DEL_FILE) Makefile


check: first

mocclean: compiler_moc_header_clean compiler_moc_source_clean

mocables: compiler_moc_header_make_all compiler_moc_source_make_all

compiler_moc_header_make_all:
compiler_moc_header_clean:
compiler_rcc_make_all:
compiler_rcc_clean:
compiler_image_collection_make_all: qmake_image_collection.cpp
compiler_image_collection_clean:
	-$(DEL_FILE) qmake_image_collection.cpp
compiler_moc_source_make_all:
compiler_moc_source_clean:
compiler_uic_make_all:
compiler_uic_clean:
compiler_yacc_decl_make_all:
compiler_yacc_decl_clean:
compiler_yacc_impl_make_all:
compiler_yacc_impl_clean:
compiler_lex_make_all:
compiler_lex_clean:
compiler_clean: 

####### Compile

main.o: main.c 
	$(CC) -c $(CFLAGS) $(INCPATH) -o main.o main.c

####### Install

install_scripts: first FORCE
	-@$(CHK_DIR_EXISTS) $(INSTALL_ROOT)/usr/pbi || $(MKDIR) $(INSTALL_ROOT)/usr/pbi/
	-$(INSTALL_FILE) .pbiwrapper $(INSTALL_ROOT)/usr/pbi/.pbiwrapper

install:   FORCE install_scripts

uninstall:   FORCE

FORCE:

