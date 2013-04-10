\ Copyright (c) 2003 Scott Long <scottl@freebsd.org>
\ Copyright (c) 2003 Aleksander Fafula <alex@fafula.com>
\ All rights reserved.
\
\ Redistribution and use in source and binary forms, with or without
\ modification, are permitted provided that the following conditions
\ are met:
\ 1. Redistributions of source code must retain the above copyright
\    notice, this list of conditions and the following disclaimer.
\ 2. Redistributions in binary form must reproduce the above copyright
\    notice, this list of conditions and the following disclaimer in the
\    documentation and/or other materials provided with the distribution.
\
\ THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
\ ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
\ IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
\ ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
\ FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
\ DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
\ OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
\ HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
\ LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
\ OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
\ SUCH DAMAGE.
\
\ $FreeBSD: src/sys/boot/forth/beastie.4th,v 1.10.2.2 2006/04/04 17:03:44 emax Exp $

marker task-beastie.4th

include /boot/screen.4th
include /boot/frames.4th

hide

variable menuidx
variable menubllt
variable menuX
variable menuY
variable promptwidth

variable bootkey
variable bootacpikey
variable bootsafekey
variable bootverbosekey
variable rundisplaywiz
variable bootsinglekey
variable escapekey
variable rebootkey
variable bootsafe_set
variable xvesa
variable xvesa_set
variable xwiz_set
variable kernelkey
variable kerncurrent
variable kerncurrent_set
variable kernold
variable kernold_set
variable kerngeneric
variable kerngeneric_set

46 constant dot

\ The BSD Daemon.  He is 19 rows high and 34 columns wide
: beastie-logo ( x y -- )
\ 2dup at-xy ."               [1;31m,        ," 1+
\ 2dup at-xy ."              /(        )`" 1+
\ 2dup at-xy ."              \ \___   / |" 1+
\ 2dup at-xy ."              /- [37m_[31m  `-/  '" 1+
\ 2dup at-xy ."             ([37m/\/ \[31m \   /\" 1+
\ 2dup at-xy ."             [37m/ /   |[31m `    \" 1+
\ 2dup at-xy ."             [34mO O   [37m) [31m/    |" 1+
\ 2dup at-xy ."             [37m`-^--'[31m`<     '" 1+
\ 2dup at-xy ."            (_.)  _  )   /" 1+
\ 2dup at-xy ."             `.___/`    /       " 1+
\ 2dup at-xy ."               `-----' /" 1+
\ 2dup at-xy ."  [33m<----.[31m     __ / __   \" 1+
\ 2dup at-xy ."  [33m<----|====[31mO)))[33m==[31m) \) /[33m====|" 1+
\ 2dup at-xy ."  [33m<----'[31m    `--' `.__,' \" 1+
\ 2dup at-xy ."               |        |" 1+
\ 2dup at-xy ."                \       /       /\" 1+
\ 2dup at-xy ."           [36m______[31m( (_  / \______/" 1+
\ 2dup at-xy ."         [36m,'  ,-----'   |" 1+
\ at-xy ."         `--{__________) [0m"
;

: beastiebw-logo ( x y -- )
\	2dup at-xy ."              ,        ," 1+
\	2dup at-xy ."             /(        )`" 1+
\	2dup at-xy ."             \ \___   / |" 1+
\	2dup at-xy ."             /- _  `-/  '" 1+
\	2dup at-xy ."            (/\/ \ \   /\" 1+
\	2dup at-xy ."            / /   | `    \" 1+
\	2dup at-xy ."            O O   ) /    |" 1+
\	2dup at-xy ."            `-^--'`<     '" 1+
\	2dup at-xy ."           (_.)  _  )   /" 1+
\	2dup at-xy ."            `.___/`    /" 1+
\	2dup at-xy ."              `-----' /" 1+
\	2dup at-xy ." <----.     __ / __   \" 1+
\	2dup at-xy ." <----|====O)))==) \) /====" 1+
\	2dup at-xy ." <----'    `--' `.__,' \" 1+
\	2dup at-xy ."              |        |" 1+
\	2dup at-xy ."               \       /       /\" 1+
\	2dup at-xy ."          ______( (_  / \______/" 1+
\	2dup at-xy ."        ,'  ,-----'   |" 1+
\	     at-xy ."        `--{__________)"
;

: fbsdbw-logo ( x y -- )
	2dup at-xy ."     ____  ______" 1+
	2dup at-xy ."    / __ \/ ____/" 1+
	2dup at-xy ."   / /_/ / /" 1+
	2dup at-xy ."  / ____/ /___" 1+
	2dup at-xy ." /_/    \____/" 1+
	2dup at-xy ."     ____ _____ ____" 1+
	2dup at-xy ."    / __ ) ___// __ \" 1+
	2dup at-xy ."   / __  \__ \/ / / /" 1+
	2dup at-xy ."  / /_/ /__/ / /_/ /" 1+
	     at-xy ." /_____/____/_____/"
;

: print-logo ( x y -- )
	s" loader_logo" getenv
	dup -1 = if
		drop
		fbsdbw-logo
		exit
	then
	2dup s" fbsdbw" compare-insensitive 0= if
		2drop
		fbsdbw-logo
		exit
	then
	2dup s" beastiebw" compare-insensitive 0= if
		2drop
		beastiebw-logo
		exit
	then
	2dup s" beastie" compare-insensitive 0= if
		2drop
		beastie-logo
		exit
	then
	2dup s" none" compare-insensitive 0= if
		2drop
		\ no logo
		exit
	then
	2drop
	fbsdbw-logo
;

: acpienabled? ( -- flag )
	s" acpi_load" getenv
	dup -1 = if
		drop false exit
	then
	s" YES" compare-insensitive 0<> if
		false exit
	then
	s" hint.acpi.0.disabled" getenv
	dup -1 <> if
		s" 0" compare 0<> if
			false exit
		then
	else
		drop
	then
	true
;

: printmenuitem ( -- n )
	menuidx @
	1+ dup
	menuidx !
	menuY @ + dup menuX @ swap at-xy
	menuidx @ .
	menuX @ 1+ swap at-xy
	menubllt @ emit
	menuidx @ 48 +
;

: options-menu ( -- )
	0 menuidx !
	dot menubllt !
	8 menuY !
	5 menuX !
	clear
	24 1 at-xy ."     ____  ______    ____ _____ ____"
	24 2 at-xy ."    / __ \/ ____/   / __ ) ___// __ \"
	24 3 at-xy ."   / /_/ / /       / __  \__ \/ / / /"
	24 4 at-xy ."  / ____/ /___    / /_/ /__/ / /_/ /"
	24 5 at-xy ." /_/    \____/   /_____/____/_____/"
	24 6 at-xy ."  "
	24 7 at-xy ."   Press any key for boot options"
;

: kernels-menu ( -- )
	0 menuidx !
	dot menubllt !
	8 menuY !
	5 menuX !
	clear
	46 4 print-logo
	43 15 2 2 box
	13 6 at-xy ." Select kernel to boot in"
	printmenuitem ."  Current kernel        (kernel)" kerncurrent !
	s" kernelold_show" getenv
	dup -1 <> if
		s" YES" compare-insensitive 0 = if
			printmenuitem ."  Previous kernel       (kernel.old)" kernold !
		then
	else
		drop
	then
	s" kernelgeneric_show" getenv
	dup -1 <> if
		s" YES" compare-insensitive 0 = if
			printmenuitem ."  Generic PC-BSD kernel (kernel.pcbsd)" kerngeneric !
		then
	else
		drop
	then
	menuX @ 15 at-xy
	." Select option, [Enter] for go back"
	menuX @ 21 at-xy
;

: beastie-menu ( -- )
	-1 menuidx !
	dot menubllt !
	8 menuY !
	5 menuX !
	clear
	46 4 print-logo
	43 22 2 2 box
	13 5 at-xy ." Welcome to PC-BSD!"
	printmenuitem ."  Boot PC-BSD [default]" bootkey !
	printmenuitem ."  Boot PC-BSD in single user mode" bootsinglekey !
	printmenuitem ."  Boot PC-BSD with verbose logging" bootverbosekey !
	s" arch-i386" environment? if
		drop
		printmenuitem ."  Toggle ACPI " bootacpikey !
		acpienabled? if
			." (Enabled)"
		else
			." (Disabled)"
		then
	else
		-2 bootacpikey !
	then
	printmenuitem ."  Toggle Safe Mode " bootsafekey !
	bootsafe_set @ 1 = if
		." (Enabled)"
	else
		." (Disabled)"
	then
	printmenuitem ."  Toggle X in VESA mode " xvesa !
	xvesa_set @ 1 = if
		." (Enabled)"
	else
		." (Disabled)"
	then
	printmenuitem ."  Run the Display Wizard " rundisplaywiz !
	xwiz_set @ 1 = if
		." (Enabled)"
	else
		." (Disabled)"
	then
	printmenuitem ."  Escape to loader prompt" escapekey !
	s" kernelmenu_show" getenv
	dup -1 <> if
		s" YES" compare-insensitive 0 = if
			printmenuitem ."  Select kernel " kernelkey !
			kerngeneric_set @ 1 = if
				." (kernel.pcbsd)"
			then
			kernold_set @ 1 = if
				." (kernel.old)"
			then
		then
	else
		drop
	then
	printmenuitem ."  Reboot" rebootkey !
	menuX @ 20 at-xy
	." Select option, [Enter] for default"
	menuX @ 21 at-xy
;

: tkeynotimer
	seconds +
	begin 1 while
		key? if
			drop
			key
			exit
		then
	50 ms
	repeat
;

: tkeyhidetimer
	seconds +
	begin 1 while
		over 0<> if
			dup seconds u< if
				drop
				-1
				exit
			then
		then
		key? if
			drop
			key
			exit
		then
	50 ms
	repeat
;


set-current

: beastie-start
	s" beastie_disable" getenv
	dup -1 <> if
		s" YES" compare-insensitive 0= if
			exit
		then
	else
		drop
	then
	s" NO" s" xvesa" setenv
	0 bootsafe_set !
	0 xvesa_set !
	0 xwiz_set !
	1 kerncurrent_set !
	0 kernold_set !
	0 kerngeneric_set !
	s" autoboot_delay" getenv
	dup -1 = if
		s" 02" s" autoboot_delay" setenv
	then
	s" autoboot_delay" getenv
	dup -1 = if
		drop
		10
	else
		0 0 2swap >number drop drop drop
	then
	begin
	s" autoboot_delay" getenv
	dup -1 <> if
		s" NO" compare-insensitive 0= if
			beastie-menu
			dup tkeynotimer
			0 25 at-xy
			dup 32 = if nip 0 swap then
			dup -1 = if 0 boot then
			dup 13 = if 0 boot then
			dup bootkey @ = if 0 boot then
			dup bootacpikey @ = if
				acpienabled? if
					s" acpi_load" unsetenv
					s" 1" s" hint.acpi.0.disabled" setenv
					s" 1" s" loader.acpi_disabled_by_user" setenv
				else
					s" YES" s" acpi_load" setenv
					s" 0" s" hint.acpi.0.disabled" setenv
				then
			then
			dup bootsafekey @ = if
				bootsafe_set @ 1 = if
					s" 0" s" hw.ata.ata_dma" setenv
					s" 0" s" hw.ata.atapi_dma" setenv
					s" 0" s" hw.ata.wc" setenv
					s" 0" s" hw.eisa_slots" setenv
					s" 1" s" hint.kbdmux.0.disabled" setenv
					0 bootsafe_set !
				else
					s" 1" s" hw.ata.ata_dma" setenv
					s" 1" s" hw.ata.atapi_dma" setenv
					s" 1" s" hw.ata.wc" setenv
					s" 1" s" hw.eisa_slots" setenv
					s" 0" s" hint.kbdmux.0.disabled" setenv
					1 bootsafe_set !
				then
			then
			dup bootverbosekey @ = if
				s" YES" s" boot_verbose" setenv
				0 boot
			then
			dup xvesa @ = if
				xvesa_set @ 1 = if
					s" NO" s" xvesa" setenv
					0 xvesa_set !
				else
					s" YES" s" xvesa" setenv
					1 xvesa_set !
				then
			then
			dup rundisplaywiz @ = if
				xwiz_set @ 1 = if
					s" NO" s" runwiz" setenv
					0 xwiz_set !
				else
					s" YES" s" runwiz" setenv
					1 xwiz_set !
				then
			then
			dup bootsinglekey @ = if
				s" YES" s" boot_single" setenv
				0 boot
			then
			dup kernelkey @ = if
				kernels-menu
				dup tkeynotimer
				dup kerncurrent @ = if
					1 kerncurrent_set !
					0 kernold_set !
					0 kerngeneric_set !
				then
				dup kerngeneric @ = if
					0 kerncurrent_set !
					0 kernold_set !
					1 kerngeneric_set !
				then
				dup kernold @ = if
					0 kerncurrent_set !
					1 kernold_set !
					0 kerngeneric_set !
				then
				0 1 unload drop
				kerncurrent_set @ 1 = if
					s" kernel" s" kernel" setenv
				then
				kerngeneric_set @  1 = if
					s" kernel.pcbsd" s" kernel" setenv
				then
				kernold_set @ 1 = if
					s" kernel.old" s" kernel" setenv
				then
			then
			dup escapekey @ = if
				2drop
				s" NO" s" autoboot_delay" setenv
				exit
			then
			rebootkey @ = if 0 reboot then
		else
			options-menu
			dup tkeyhidetimer
			dup 32 = if nip 0 swap then
			clear
			dup -1 = if 0 boot then
			s" NO" s" autoboot_delay" setenv
		then
	else
		clear
		0 boot	
	then
	again
;

previous
