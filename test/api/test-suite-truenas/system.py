import sys
import os

os.system('rm *.pyc')

def main():
  print '******WARNING******'
  warn = raw_input('This operation will destory everything including Advanced, NTPServer, and Settings etc... in System and your System will REBOOT(yes/no):')
  oper_flag = 1
  while(oper_flag <= 3):
    if oper_flag == 3:
      print 'Please re-run System test suite!'
      sys.exit(0)
    if warn == 'no' or warn == 'n':
      sys.exit(0)
    elif warn == 'yes' or warn == 'y':
      break
    elif warn !='no' and warn != 'yes' and warn != 'y' and warn !='n':
      warn = raw_input("Invalid operation! Please input 'yes' or 'no':")
      oper_flag = oper_flag + 1
      continue

if __name__ == '__main__':
  main()

import system_advanced
import system_alert
import system_email
import system_ntpserver
import system_reboot
import system_settings
import system_shutdown
import system_ssl
import system_tunable
#import system_version

print '***Running System-NTPServer ......'
system_ntpserver.put()
system_ntpserver.delete()
print ''

print '\n***Running System-Advanced ......'
system_advanced.put()
print ''

print '***Running System-Alert ......'
system_alert.get()
print ''

print '***Running System-Email ......'
system_email.get()
system_email.put()
print ''

print '***Running System-Settings ......'
system_settings.put()
print ''

print '***Running System-SSL ......'
system_ssl.put()
print ''

print '***Running System-Tunable ......'
system_tunable.put()
system_tunable.delete()
print ''

#print '***Running System-Version ......'
#system_version.get()
#print ''

#print '***Running System-Reboot/System-Shutdown ......'
#system_reboot.post()
#print ''

#print '***Running System-Shutdown ......'
#print ''
