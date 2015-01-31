import sys
import os

os.system('rm *.pyc')

def main():
  print '******WARNING******'
  warn = raw_input('This operation will destory everything including LDAP, NIS, and NT4 etc... in DirectoryService (yes/no):')
  oper_flag = 1
  while(oper_flag <= 3):
    if oper_flag == 3:
      print 'Please re-run DirectoryServices test suite!'
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

import directoryservice_activedirectory                                                                                            
import directoryservice_ldap                                                                                                       
import directoryservice_nis                                                                                                      
import directoryservice_nt4

print '\n***Running Directoryservice-ActiveDirectory ......'
directoryservice_activedirectory.put()
print ''

print '***Running Directoryservice-LDAP ......'
directoryservice_ldap.put()
print ''

print '***Running Directoryservice-NIS ......'
directoryservice_nis.put()
print ''

print '***Running Directoryservice-NT4 ......'
directoryservice_nt4.put()
print '\n'
