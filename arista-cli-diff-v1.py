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

            self.diff_generic(cmd_result_1, cmd_result_2,
                              {'index' :['NETWORK', 'MASK'],
                               'check' :['NEXT_HOP', 'INTERFACE'],})

            '''
            handle = self.get_diff_handle(cmd_name_1)
            if handle:
                handle(cmd_result_1, cmd_result_2)
            else:
                print("Can't find diff function for %s !! Skip it!" % cmd_name_1)
            '''

    def diff_show_ip_route(self, r1, r2):

        t1 = pd.DataFrame(data=r1[1:], columns=r1[0])
        t2 = pd.DataFrame(data=r2[1:], columns=r2[0])
        #t1_index = t1.set_index(['NETWORK', 'MASK', 'NEXT_HOP'])
        #t1_index = t1.set_index(['NETWORK', 'MASK', 'NEXT_HOP'])
        t1_index = t1.set_index(['NETWORK', 'MASK'])
        t2_index = t2.set_index(['NETWORK', 'MASK'])
        # join of two table with index keys to find out difference between two tables
        result_table = t1_index.join(t2_index, how='outer', lsuffix='1', rsuffix='2')

        # diff table convert to a list
        result = [result_table.columns.tolist()] + result_table.reset_index().values.tolist()

        for line in result[1:]:
            if type(line[9]) is float and math.isnan(line[9]):
                print('Missing Route: %s' % line)
            elif type(line[4]) is float and math.isnan(line[4]):
                print('New Route: %s' % line)

    def diff_generic(self, data_1, data_2, diff_conf):
        '''
        data_1 and data_2 is assumed with first row of column name and all other route with date
        diff_conf = { 'index': ['NETWORK', 'MASK'],
                      'check': ['NEXT_HOP', 'INTERFACE']
        first check if those two data are have same format

        '''
        # check if data_1 and data_2 has same format
        if not self.check_data_format(data_1, data_2, diff_conf):
            return None

        # make index based on fields based on diff_conf
        t1 = pd.DataFrame(data=data_1[1:], columns=data_1[0])
        t2 = pd.DataFrame(data=data_2[1:], columns=data_2[0])

        index = diff_conf['index']
        t1_index = t1.set_index(index)
        t2_index = t2.set_index(index)

        # make a outer join to formulate a table with all entreis
        result_table = t1_index.join(t2_index, how='outer', lsuffix='1', rsuffix='2')
        result_table = result_table.where((pd.notnull(result_table)), 'NAN')

        # diff table convert to a list
        result = [result_table.columns.tolist()] + result_table.reset_index().values.tolist()

        # find out which entry is new / missing / changed
        diff = self.get_diffs(result, diff_conf['check'])

        print("finished diff!!")
        return diff

    @staticmethod
    def get_diffs(result, check):
        # the column is appended with _1 or _2 for non-index field
        all_column = result[0]
        # find all checking pair index according to column name
        full_index = [(all_column.index(c+'1'), all_column.index(c+'2'))
                                   for c in check]
        left_index = [x[0] for x in full_index]
        right_index = [x[1] for x in full_index]

        for line in result[1:]:
            stop = False
            for i in left_index:
                if line[i] == 'NAN':
                    print('Missing Route: %s' % line)
                    stop = True
                    break
            if stop: break
            for i in right_index:
                if line[i] == 'NAN':
                    print('New Route: %s' % line)
                    stop = True
                    break
            if stop: break
            same = True
            for i,j in full_index:
                if line[i] != line[j]:
                    print('Different Route %s' % line)
                    stop = True
                    break

    @staticmethod
    def check_data_format(data_1, data_2, diff_conf):
        # check if the column name has the same contains
        if data_1[0] != data_2[0]:
            print('Column Name is not matching for those two data:\n data 1:%s \n data 2: %s' %
                  data_1, data_2)
            return False
        # check if the diff_conf using the right column name
        column_name = data_1[0]
        for conf in diff_conf.values():
            # check if conf is subset of column name
            if not frozenset(conf).issubset(frozenset(column_name)):
                print("diff_conf %s is not in %s" % (conf, column_name))
                return False
        return True








if __name__ == '__main__':
    '''
    host = 'carcore3'
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
    f2 = 'carcore3_backup_20170928110800.json'
    diff = AristaStateDiff(f1, f2)
