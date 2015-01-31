import sys
import os

os.system('rm *.pyc')

def main():
  print '******WARNING******'
  warn = raw_input('This operation will destory everything including Interface, Lagg, and Vlan etc... in Network (yes/no):')
  oper_flag = 1
  while(oper_flag <= 3):
    if oper_flag == 3:
      print 'Please re-run Network test suite!'
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

import network_globalconfiguration                                                                                            
import network_interface                                                                                                 
import network_lagg                                                                                                     
import network_vlan
import network_staticroute

print '\n***Running Network_GlobalConfiguration ......'
network_globalconfiguration.put()
print ''

#print '***Running Network_Interface ......'
#network_interface.put()
#network_interface.delete()
#print ''

#print '***Running Network_Lagg ......'
#network_lagg.post()
#network_lagg.delete()
#print ''

#print '***Running Network_StaticRoute ......'
#network_staticroute.put()
#network_staticroute.delete()
#print ''

#print '***Running Network_Vlan ......'
#network_vlan.put()
#network_vlan.delete()
#print '\n'
