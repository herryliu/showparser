#!/usr/bin/env python

import json
import getpass
import pprint
import pyeapi
import textfsm
import clitable

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

        # get json version of all commands and parse it if json version is not available
        cli_result = self.cli.get_result('json')
        for r in cli_result:
            print(r['command'])
            # default assume it parsed by Arista
            r['parser'] = 'eos'
            if r['encoding'] == 'text'and r['result']['output']:
                # need to parse the text file
                print("command %s need a parse" % r['command'])
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
        json.dump(fin_result_json, self.backup_file_json)

        return fin_result_json

    @staticmethod
    def execute_parser(template, attributes, section_data):
        #print("executing command %s" % attributes['Command'])
        #print("template directory %s" % template['Template Dir'])
        cli_table = clitable.CliTable(template['Index File'], template['Template Dir'])
        try:
            cli_table.ParseCmd(section_data, attributes)
        except clitable.CliTableError as e:
            #print("error %s" % e)
            return None
        # convert the cli_table to a list
        #print("executing command %s" % attributes['Command'])
        result = []
        for line in cli_table.table.split('\n'):
            result.append(line.split(','))
        return result

if __name__ == '__main__':

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
