#!/usr/bin/env python

import getpass
import napalm
import pprint

password = getpass.getpass('Please input your password: ')

driver = napalm.get_network_driver('napalm_eos')

device = driver(hostname='sgxcore1', username='herry', password=password)
device.open()
result = device.cli(['show version', 'show int status'])
device.close()
pprint.pprint(result)
