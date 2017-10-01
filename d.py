#!/usr/bin/env python

import pyeapi
import pandas as pd
import numpy as np
import getpass


host = 'carcore3'
username = 'herry'

command_list = ['show ip route']
password = getpass.getpass('Please input your password: ')
transport = 'https'

node = pyeapi.connect(transport=transport,
                        host=host,
                        username=username,
                        password=password,
                        return_node=True)

route_raw = node.enable(command_list)
data = route_raw[0]['result']
