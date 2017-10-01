#!/usr/bin/env python

import json
import getpass
import pprint
import pyeapi
import textfsm
import clitable
import pandas as pd
import math

from datetime import datetime

TEMPLATE_INDEX_DIR = '/scratch/herry/git/code/systems-lib/python/systemslib/net/Arista/template/'
TEMPLATE_INDEX_FLIE = 'index'

class AristaCli(object):
    def __init__(self, device, username='', password='', transport='https', command_list=[]):
        self.device = device
        self.username = username
        self.transport = transport
        self.command_list = command_list

        if not password:
            # get password from console
            self.password = getpass.getpass('Please input your password: ')
        else:
            self.password = password

        self.node = pyeapi.connect(transport=self.transport,
                                host=self.device,
                                username=self.username,
                                password=self.password,
                                return_node=True)

    def set_command_list(self, c_list):
        if c_list:
            self.command_list = c_list if type(c_list) == list else list(c_list)

    def get_result(self, encoding):
        if self.command_list:
            return(self.node.enable(self.command_list, encoding=encoding))
        return None

class AristaStateBackup(object):
    def __init__(self, device, username='', password='', command_list=[], backup_file_name=''):
        self.device = device
        self.username = username
        self.password = password

        self.command_list = command_list
        if not backup_file_name:
            self.backup_file_text = open(self.device + "_backup_" + datetime.now().strftime('%Y%m%d%H%M%S') +
                                    ".txt", 'w')
            self.backup_file_json = open(self.device + "_backup_" + datetime.now().strftime('%Y%m%d%H%M%S') +
                                    ".json", 'w')
        else:
            self.backup_file_text = open(backup_file_name+".txt", 'w')
            self.backup_file_json = open(backup_file_name+".json", 'w')


        self.cli = AristaCli(self.device, username=self.username, password=self.password,
                       command_list=self.command_list)

    def set_command_list(self, c_list):
        if c_list:
            self.command_list = c_list if type(c_list) == list else list(c_list)

    def get_status(self):
        fin_result_text = []
        fin_result_json = []

        # get text version of all commands and save it into a text backup file
        cli_result = self.cli.get_result('text')

        if cli_result:
            for r in cli_result:
                self.backup_file_text.write("--------------- %s -------------\n" % r['command'])
                #for line in r['result']['output'].split('\n'):
                for line in r['result']['output']:
                    #self.backup_file_text.write(line+'\n')
                    self.backup_file_text.write(line)
                self.backup_file_text.write("--------------------------------\n")

                fin_result_text.append(r)

        for r in cli_result:
            print(r['command'])
            # default assume it parsed by Arista
            r['parser'] = 'google'
            attributes = {'Command': r['command'], 'Vendor': 'Arista'}
            template = {'Template Dir': TEMPLATE_INDEX_DIR, 'Index File': TEMPLATE_INDEX_FLIE}
            parse_result =  AristaStateBackup.execute_parser(template, attributes, r['result']['output'])
            if parse_result:
                r['result'] = parse_result
                r['encoding'] = 'list'
            else:
                print("Don't know how to parse %s. But keep it raw !!" % r['command'])
            fin_result_json.append(r)
        json.dump(fin_result_json, self.backup_file_json, indent=2)

        return fin_result_json

    @staticmethod
    def execute_parser(template, attributes, section_data):
        cli_table = clitable.CliTable(template['Index File'], template['Template Dir'])
        try:
            cli_table.ParseCmd(section_data, attributes)
        except clitable.CliTableError as e:
            return None
        result = []
        for line in cli_table.table.split('\n'):
            result.append(line.split(', '))
        return result

class AristaStateDiff(object):
    def __init__(self, first, second):
        self.first_file_name = first
        self.second_file_name = second
        self.first_data = json.load(open(self.first_file_name))
        self.second_data = json.load(open(self.second_file_name))
        self.diff_handle = {}

        self.register_diff_handle()

        self.diff_state()

    def register_diff_handle(self):
        self.diff_handle['show ip route'] = self.diff_show_ip_route

    def get_diff_handle(self,cmd):

        if cmd in self.diff_handle.keys():
            return self.diff_handle[cmd]

    def diff_state(self):
        for cmd1, cmd2 in zip(self.first_data, self.second_data):
            # get the data from two json file
            cmd_name_1 = cmd1['command']
            cmd_result_1 = cmd1['result']
            cmd_name_2 = cmd2['command']
            cmd_result_2 = cmd2['result']

            if cmd_name_1 != cmd_name_2:
                print("Can't compare %s with %s!!", (cmd_name_1, cmd_name_2))
                continue

            print("diff command %s" % cmd_name_1)

            handle = self.get_diff_handle(cmd_name_1)

            if handle:
                handle(cmd_result_1, cmd_result_2)

    def diff_show_ip_route(self, r1, r2):

        t1 = pd.DataFrame(data=r1[1:], columns=r1[0])
        t2 = pd.DataFrame(data=r2[1:], columns=r2[0])
        t1_index = t1.set_index(['NETWORK', 'MASK', 'NEXT_HOP'])
        t2_index = t2.set_index(['NETWORK', 'MASK', 'NEXT_HOP'])
        # join of two table with index keys to find out difference between two tables
        result_table = t1_index.join(t2_index, how='outer', lsuffix='1', rsuffix='2')

        # diff table convert to a list
        result = [result_table.columns.tolist()] + result_table.reset_index().values.tolist()

        for line in result[1:]:
            if type(line[9]) is float and math.isnan(line[9]):
                print('Missing Route: %s' % line)
            elif type(line[4]) is float and math.isnan(line[4]):
                print('New Route: %s' % line)

if __name__ == '__main__':
    host = 'jpncore2'
    username = 'herry'
    command_to_do = ['show version',
                     'show ip bgp',
                    ]
    command_to_do =[
                    'show ip route',
                    'show ip bgp',
                    'show ip bgp summary',
                    'show ip ospf database',
                    'show ip pim neighbor',
                    'show ip pim interface',
                    'show ip mroute',
                    'show interfaces status',
                    'show ip interface brief',
                    'show lldp neighbors detail',
                    'show mac address-table',
                    'show ip arp',
                    'show ip mfib',
                    ]
    backup = AristaStateBackup(host, username=username, command_list=command_to_do)
    backup.get_status()
    '''
    f1 = 'carcore3_backup_20170928005037.json'
    f2 = 'carcore3_backup_20170928005037.json'
    diff = AristaStateDiff(f1, f2)
    '''
