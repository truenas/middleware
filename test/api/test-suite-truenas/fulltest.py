def main():
  print '******WARNING******'
  warn = raw_input('******Warning******This operation will destory everything on your FreeNAS system and set configuration on it. Contiune?(yes/no):')
  oper_flag = 1
  while(oper_flag <= 3):
    if oper_flag == 3:  
      print 'Please re-run Fulltest suite!'
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

# SYSTEM
print '***Running System Test Suite***'
import system

# STORAGE
print '***Running Storage Test Suite***'
import storage

# TASKS
#print '***Running Tasks Test Suite***'
#import tasks

# SERVICES
print '***Running Services Test Suite'
import services

# SHARING
print '***Running Sharing Test Suite***'
import sharing

# DirectoryService
print '***Running DirectoryService Test Suite***'
import directoryservice

# Network
print '***Running Network Test Suite***'
import network

# Plugins
print '***Running Plugins Test Suite***'
import plugins
plugins.operating()
