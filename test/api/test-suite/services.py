import sys
import os

os.system('rm *.pyc')

def main():
  print '******WARNING******'
  warn = raw_input('This operation will destory everything including AFP, CIFS, and FTP etc... in Services and Volume in Storage (yes/no):')
  oper_flag = 1
  while(oper_flag <= 3):
    if oper_flag == 3:
      print 'Please re-run Services test suite!'
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

import services_afp
import services_cifs
import services_domaincontroller
import services_dynamicdns
import services_ftp
import services_lldp
import services_nfs   
import services_rsyncd  
import services_rsyncmod
#import services_services
import services_smart
import services_snmp 
import services_ssh 
import services_tftp
import services_ups 

print '\n***Running Services-AFP ......'
services_afp.put()
print ''

print '***Running Services-CIFS......'
services_cifs.put()
print ''

print '***Running Services-DomainController ......'
services_domaincontroller.put()
print ''

print '***Running Services-DynamicDNS ......'
services_dynamicdns.put()
print ''

print '\n***Running Services-ftp ......'
services_ftp.put()
print ''

print '\n***Running Services-LLDP ......'
services_lldp.put()
print ''

print '\n***Running Services-nfs ......'
services_nfs.put()
print ''

print '\n***Running Services-Rsyncd ......'
services_rsyncd.put()
print ''

print '***Running Services-RsyncMod ......'
services_rsyncmod.put()
services_rsyncmod.delete()
print ''

print '\n***Running Services-SMART ......'
services_smart.put()
print ''

print '\n***Running Services-SNMP ......'
services_snmp.put()
print ''

print '\n***Running Services-SSH ......'
services_ssh.put()
print ''

print '\n***Running Services-TFTP ......'
services_tftp.put()
print ''

print '\n***Running Services-UPS ......'
services_ups.put()
print ''

