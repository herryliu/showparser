#!/usr/bin/env python

import getpass
import pprint
import pyeapi

password = getpass.getpass('Please input your password: ')
transport = 'https'
host = 'carcore3'
username = 'herry'

node = pyeapi.connect(transport=transport, host=host, username=username, password=password, return_node=True)

#result = node.execute(['show version', 'show ip route'])
command_to_do = ['show version',
                 'show ip route',
                 'show ip bgp summary',
                 'show ip bgp',
                 'show ip mroute',
                 'show ip mfib',
                 'show interfaces status',
                ]
result = node.enable(command_to_do)

#pprint.pprint(result)

for r in result:
    print(" command: %s --> return type: %s" % (r['command'], r['encoding']))
