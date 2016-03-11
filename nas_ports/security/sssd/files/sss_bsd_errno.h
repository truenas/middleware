/*
    SSSD

    Authors:
        Lukas Slebodnik <lslebodn@redhat.com>

    Copyright (C) 2013 Red Hat

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#ifndef SSS_BSD_ERRNO_H_
#define SSS_BSD_ERRNO_H_

#include <errno.h>

#define BSD_ERR_MASK (0xB5DE <<16)

#ifndef EUCLEAN
#define EUCLEAN (BSD_ERR_MASK | 117)
#endif
#ifndef EMEDIUMTYPE
#define EMEDIUMTYPE (BSD_ERR_MASK | 124)
#endif
#ifndef EOWNERDEAD
#define EOWNERDEAD (BSD_ERR_MASK | 130)
#endif
#ifndef ECONNRESET
#define ECONNRESET (BSD_ERR_MASK | 104)
#endif
#ifndef ETIMEDOUT
#define ETIMEDOUT (BSD_ERR_MASK | 110)
#endif
#ifndef ENODATA
#define ENODATA (BSD_ERR_MASK | 61)
#endif
#ifndef ETIME
#define ETIME (BSD_ERR_MASK | 62)
#endif
#ifndef ELIBACC
#define ELIBACC (BSD_ERR_MASK | 79)
#endif
#ifndef ELIBBAD
#define ELIBBAD (BSD_ERR_MASK | 80)
#endif

#endif /* SSS_BSD_ERRNO_H_ */
