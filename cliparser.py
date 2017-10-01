#!/usr/bin/env python
from __future__ import print_function
from __future__ import absolute_import

import os
import re
import gzip
import logging
import pprint

import textfsm
import clitable

logging.basicConfig()
log = logging.getLogger(__name__) # pylint: disable=C0103
TEMPLATE_INDEX_DIR = '/systems/lib/systemslib/net/Arista/template'

class LogDataException(Exception):
    '''
    Raised when logs don't have the section we're looking for
    '''
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

class AristaSTParser(object):
    '''
    Class to parse a Cisco 'show tech' output

    Usage:
    parser = AristaSTParser('Arista_Show_Tech_File_Name.gz')
    # full parsed info
    full = praser.get_full_result()
    # only interface related info
    interface = parser.get_interface_result()
    # only system wise info
    system = parser.get_system_result()
    # the parser output for different show command
    parser = praser.get_parser_result()
    '''

    '''
    Internal data structures:
    self.log_file --> show tech file handler
    self.st_result --> the parsed result for different show commands
    self.result --> consolidated result mainly grouped in interface/system
    self.section_parser --> the list of all show commands and associated parser
    self.section_parser_ordered --> same as above but will the order appears in log file
    self.all_command --> all command in the show tech file up to last registered handler
    '''
    def __init__(self, filename, zipped=True, parse=True, index_file='index'):
        # check if the log file is a Cisco one
        if AristaSTParser.is_arista_log(filename, zipped):
            self.log_file = gzip.open(filename) if zipped else open(filename)
        # initalize a few internal data structure
        self.index_file = index_file
        if os.path.exists('./template'):
            # use the local template directory
            self.template_dir = os.path.realpath('./template')
            print(self.template_dir)
        else:
            self.template_dir = TEMPLATE_INDEX_DIR


        self.all_command = []
        self.section_parser = {}
        self.section_parser_ordered = []
        self.parsed = False
        # raw outoput from different show commands
        self.st_result = {}
        # consolidated info
        self.result = {}
        if parse:
            # parse the file during the class initialization
            self.parse_log_file()

    def parse_log_file(self):
        '''
        parse the show tech file for all defined parsers in template index file
        '''
        # read in logfile and try to find out each show tech section
        # and pass the section to defined template for parsing
        section = re.compile(r'------------- (show .*) -------------')
        section_found = False
        section_data = ''
        command = ''

        for line in self.log_file:
            m = section.match(line)
            if m and not section_found:
                command = m.group(1)
                print("command is %s" % command)
                # append the command into all command list
                self.all_command.append(command)
                # continue to find the end session
                section_found = True
                section_data = ''
            elif m and section_found:
                # end of session and excute the parser
                attributes = {'Command': command, 'Vendor': 'Arista'}
                template = {'Template Dir': self.template_dir, 'Index File': self.index_file}
                result =  AristaSTParser.execute_parser(template, attributes, section_data)
                # get the parser result and save into st_result
                if result:
                    self.st_result[command] = result
                # reset the file pointer to rewind one lien
                self.log_file.seek(-len(line), 1)
                section_found = False

            if section_found:
                section_data = section_data + line

        pprint.pprint(self.st_result)
        self.parsed = True
        # consolidate the result by combine mulitple parsed section info into one dictionary
        #self.consolidate_info()

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

    def consolidate_info(self):
        '''
        combine various info into more structured way
        '''
        # setup short name for each show result
        st = {}
        st['si'] = self.st_result['show interface']
        st['sib'] = self.st_result['show interface brief']
        st['sitd'] = self.st_result['show interface transceiver details']
        st['sln'] = self.st_result['show lldp neighbors']
        st['se'] = self.st_result['show environment']
        st['sinv'] = self.st_result['show inventory']
        st['sv'] = self.st_result['show version']

        # interface related info
        self.result['Interface'] = {}
        # populate it with 'show interface' command info first
        self.result['Interface'] = st['si']
        for intf in self.result['Interface']:
            # add 'show interface tranciever details' into each interface
            if intf in st['sitd']:
                self.result['Interface'][intf].update(st['sitd'][intf])
            # add 'show interface brief' into each interface
            # find the full interface name from short-hand version
            test = [i for i in st['sib'] if self._compare_int_name(intf, i)]
            if test:
                self.result['Interface'][intf].update(st['sib'][test[0]])
            # add 'show lldp neighbors' info into interface
            test = [i for i in st['sln'] if self._compare_int_name(intf, i)]
            if test:
                self.result['Interface'][intf].update(st['sln'][test[0]])

        # make system related info
        self.result['System'] = {}
        self.result['System']['Environmental'] = st['se']
        self.result['System']['Inventory'] = st['sinv']
        self.result['System']['Version'] = st['sv']

        # copy in all other raw result
        self.result['Parser'] = {}
        for i in self.st_result:
            self.result['Parser'][i] = self.st_result[i]

    def get_full_result(self):
        '''
        return full info
        '''
        if self.parsed:
            return self.result

    def get_interface_result(self):
        '''
        return interface info
        '''
        if self.parsed:
            return self.result['Interface']

    def get_system_result(self):
        '''
        return system info
        '''
        if self.parsed:
            return self.result['System']

    def get_parser_result(self):
        '''
        return parser info
        '''
        if self.parsed:
            return self.result['Parser']

    def register_all_section_parser(self):
        '''
        regist all parsers to related section
        '''
        self.register_section_parser('show ip route detail', self.parse_show_ip_route_detail)

    def register_section_parser(self, section, handler):
        '''
        register one parser to section list
        '''
        self.section_parser[section] = handler

    def parse_again_log_file(self):
        '''
        parse the show tech file with all parser registered
        '''
        # put the file pointer back to beginning
        self.log_file.seek(0, 0)
        for item in self.section_parser_ordered:
            # execute the parser in sequnce recorded before
            item[1](item[0])

    @staticmethod
    def is_arista_log(filename, zipped=True):
        '''
        check if it is cisco show tech file
        '''
        file_handle = gzip.open(filename) if zipped else open(filename)
        try:
            head = [next(file_handle) for _ in range(50)]
        except IOError as exception:
            print("Unable to open file %s reason %s" % (filename, exception))
            return None
        regex = re.compile(r'Arista DCS-')
        return len([i for i, l in enumerate(head) if regex.match(l)]) > 0

    def _get_log_snippet(self, start='', end=''):
        '''
        return a list of matched section between start and end string
        '''
        result = []
        file_handle = self.log_file
        record_mod = False
        seek_back_len = 0
        for line in file_handle:
            if not record_mod:
                if line.startswith(start):
                    record_mod = True
            elif line.startswith(end):
                seek_back_len = len(line)
                break
            else:
                result.append(line)
        # the last read of ending line might be the first match line for next read
        # move the file pointer back for next search
        file_handle.seek(-seek_back_len, 1)
        return result

    @staticmethod
    def _filter_snippet(section, header, footer, remain=False):
        '''
        find the section by providing a list of header/footer patterns
        '''
        #construct the header/footer pattern
        #both header and footer is a list
        #header will match all list members in sequence before declare a match
        #footer is simply one line match any member in the list
        if not section:
            raise LogDataException("No Data To Be Process")
        header_match = len(header)
        p_header = [re.compile(h) for h in header]
        p_footer = [re.compile(f) for f in footer]
        h_match_c = 0
        match_lines = []
        match_lines_header = []

        for num, line in enumerate(section):
            if h_match_c != header_match:
                # try to match the header
                if p_header[h_match_c].search(line):
                    h_match_c += 1
                    match_lines_header.append(line)
                else:
                    h_match_c = 0
            else:
                # header is matched and start to process each line until the footer
                see_footer = False
                for pf in p_footer:
                    if pf.match(line):
                        see_footer = True
                        match_lines_footer = [line]
                        #break
                if not see_footer:
                    # append the line for return
                    match_lines.append(line)
                else:
                    return match_lines if not remain else (match_lines, section[num+1:],
                                                           match_lines_header, match_lines_footer)

    @staticmethod
    def _compare_int_name(n1, n2):
        '''
        check if two interface name is shorform of each other
        e.g. Ethernet1/2 and Eth1/2
        '''
        n1_prefix, n1_num = re.match(r'(\D+)(\d.*)', n1).group(1, 2)
        n2_prefix, n2_num = re.match(r'(\D+)(\d.*)', n2).group(1, 2)

        if (n1_prefix.find(n2_prefix) or n2_prefix.find(n1_prefix)) and (n1_num == n2_num):
            log.debug("name match!!")
            return True
        return False

    @staticmethod
    def _find_int_in_list(int_name, int_list):
        '''
        find the one interface name in a list evne if it's a short form
        '''
        for name in int_list:
            if AristaSTParser._compare_int_name(int_name, name):
                return name
        return None
