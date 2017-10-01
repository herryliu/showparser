#!/usr/bin/env python

import json

def routing_diff(json1, json2):

    json_data_1 = json.load(open(json1))
    json_data_2 = json.load(open(json2))

    route_raw_1 = json_data_1[1:]
    route_raw_2 = json_data_2[1:]

    route_list_1 = [ tupple(r[1,2]), [ r[



if __name__ == '__main__':
    json_file_1 = 'carcore3_backup_20170927103453.json'
    json_file_2 = 'carcore3_backup_20170927223524.json'

    routing_diff(json_file_1, json_file_2)
