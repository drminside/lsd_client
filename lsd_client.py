# -*- coding: utf-8 -*-

"""
Name: Compliance Test LSD Client for LSD server test
File Name: lsd_client.py
version: 1.0
History
    Created by Ahram Oh(aroh@drminside.com) on 06.27.2016 v0.1
    Updated by Ahram Oh(aroh@drminside.com) on 09.08.2016 v1.0
Files: lsd_client.py(Script file for test), json_schema_lsd.json(For check validation of Status document)
Tools: Python 3.5.2(Python software Foundation, Interpreter), PyCharm 2016.2.2 (JetBrain, IDE)
Dependency: pytz(MIT license), jsonschema(MIT)
Prerequisites: epub files with LSD links provided by target LCP server(The Server must provide also LSDs associated with epub files)
Detail: This script is used for verifying if a LSD server is compliant with LSD v1.0 specification
    Usage
     $ python lsd_client.py -i %interaction_name -d %device_id -n %device_name -e %end_date $epub_file_name 
       %interaction_name : which is one of following ones
         - fetch : fetch LSD from the server whose address is specified in the $epub_file_name
         - fetch_license : fetch License Document from the server whose address is specified in the LSD linked in $epub_file_name
         - register : request 'register' interaction to the server whose address is specified in the $epub_file_name
         - renew : request 'renew' interaction to the server whose address is specified in the $epub_file_name
         - return : request 'return' interaction to the server whose address is specified in the $epub_file_name         -
       %device_id : device id
       %device_name : device name
       %end_date : expired date
       %epub_file_name : specific epub_file which is provided by server to test an LSD interaction
"""

import traceback

import pip
import importlib
import sys
import os
import json
import http.client

import time

from urllib.parse import urlparse, quote
from datetime import datetime, timedelta
from zipfile import ZipFile

from colorama import init, Fore

if importlib.util.find_spec('pytz') is None:
    pip.main(['install', 'pytz'])
timezone = importlib.import_module(name='pytz').timezone

if importlib.util.find_spec('jsonschema') is None:
    pip.main(['install', 'jsonschema'])
json_validate = importlib.import_module(name='jsonschema').validate
exceptions = importlib.import_module(name='jsonschema').exceptions


def request_license_document(status_document):
    """
    Args:
        status_document (dict): A LSD with link url for License Document

    Returns:
        str: Message that based on http status code.
        str: License Document that received from server.
    """
    try:
        license_link = status_document['links']['license']['href']

        url = urlparse(license_link)
        conn = http.client.HTTPConnection(url[1])
        conn.request('GET', url[2])

        with conn.getresponse() as result:
            return result.read().decode()
    except Exception as e:
        return "Function: get_status\nMessage: " + '\n'.join(traceback.format_exception(Exception, e, None)), ""


def do_register(license_document, device_id, device_name):
    """
    Args:
        license_document (dict): A License Document with link url for LSD.
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        str: Result message for "request register" interaction.
    """
    try:
        status_document = get_status_document(license_document, device_id, device_name)
        if status_document['status'] != 'ready':
            return "do_register: This epub file status is {}".format(status_document['status'])

        code, response_data = request_register(status_document, device_id,
                                               device_name)
        return eval_register_result(code, status_document,
                                    json.loads(response_data))
    except Exception as e:
        return "Function: do_register\nMessage: " + '\n'.join(traceback.format_exception(Exception, e, None))


def request_register(status_document, device_id, device_name):
    """
    Args:
        status_document (dict): A LSD with link url for License Document
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        int: Http status code for server response.
        str: Server response value such as error message.
    """
    if device_id is None or device_name is None:
        raise RuntimeError
    activate_link = generate_query(status_document['links']['register']['href'],
                                   device_id=device_id, device_name=device_name)
    method = 'POST'
    url = urlparse(activate_link)
    conn = http.client.HTTPConnection(url[1])
    conn.request(method, url[2] + '?' + url[4])

    with conn.getresponse() as result:
        return result.status, result.read().decode()


def eval_register_result(http_code, old_status_document, response_value):
    """
    Args:
        http_code (int): Http status code for server response after "request register".
        old_status_document (dict): Current Status Document before doing "request register".
        response_value (dict): Response message which is status document when http_code is 200, or error message.

    Returns:
        str: Evaluation result message. This message describe followings, server did normally process about request, license, and status document from server are correctly renewal.
    """
    if http_code == 200:
        result_message = "Server response is 200"
        old_updated_status_time = convert_time_to_utc(
            old_status_document['updated']['status'])
        new_updated_status_time = convert_time_to_utc(
            response_value['updated']['status'])

        if response_value['status'] != 'active' \
                or new_updated_status_time <= old_updated_status_time:
            result_message += "\nWrong response received."

        return result_message
    elif http_code == 400 or http_code >= 500 or http_code < 600:
        return "Server response is {}\n{}\n{}".format(str(http_code), response_value['type'], response_value['title'])
    else:
        return "Unknown response code."


def do_renew(license_document, end_date, device_id, device_name):
    """
    Args:
        license_document (dict): License Document.
        end_date (str): License expired date requested by client.
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        str: Message of evaluation result about "request renew".
    """
    try:
        status_document = get_status_document(license_document, device_id, device_name)
        if status_document['status'] != 'active':
            return "do_renew: License is not registration."
        # check validation of end_date format using exception handler
        convert_time_to_utc(end_date)
        # Need to wait for different timestamp between old status document(//updated/status/) and new one(same path)
        time.sleep(1)

        http_code, result = request_renew(status_document, end_date,
                                          device_id=device_id,
                                          device_name=device_name)
        json_resp_data = json.loads(result)

        if "type" not in json_resp_data:
            new_lic_str = request_license_document(json_resp_data)
            new_license = json.loads(new_lic_str)
        else:
            new_license = dict()

        return eval_renew_result(http_code, json_resp_data, status_document,
                                 new_license, license_document, end_date)

    except Exception as e:
        return "Function: do_renew\nMessage: " + '\n'.join(traceback.format_exception(Exception, e, None))


def request_renew(status_document, end_date, device_id, device_name):
    """
    Args:
        status_document (dict): Status Document
        end_date (str): License expired date requested by client.
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        int: Http status code about server response
        str: Server response message which is Status Document or error message
    """
    if end_date is None:
        raise RuntimeError("end_date is None")

    renew_object = status_document['links']['renew']
    renew_link = str()
    for renew in renew_object:
        if 'type' in renew and renew['type'] == "application/vnd.readium.lcp.license-1.0+json":
            renew_link = renew['href']

    renew_link = generate_query(renew_link, device_id=device_id,
                                device_name=device_name,
                                end_date=quote(end_date))
    method = 'PUT'
    url = urlparse(renew_link)
    conn = http.client.HTTPConnection(url[1])
    conn.request(method, url[2] + '?' + url[4])

    with conn.getresponse() as result:
        return result.status, result.read().decode()


def eval_renew_result(http_code, response_value, old_status_document,
                      new_license_document, old_license_document,
                      new_end_date):
    """
    Args:
        http_code (int): http status code about "request renew".
        response_value (dict): Response value, either new status document or error message structed json.
        old_status_document (dict): Current Status Document before doing "request renew".
        new_license_document (dict): Updated License Document after doing "request renew".
        old_license_document (dict): Old License document from epub file
        new_end_date (str): Newly expired date of license requested by client.

    Returns:
        str: Result message that describe correctly done of process or not, and new license document and status document is correctly renewal.
    """
    if http_code == 200:
        # status: check updated/license date between old and new
        old_status_updated = convert_time_to_utc(old_status_document['updated']['license'])
        new_status_updated = convert_time_to_utc(response_value['updated']['license'])
        if old_status_updated >= new_status_updated:
            return "Updated date in status document is not updated"

        # license: check rights/end and new_date
        new_rights_date = convert_time_to_utc(new_license_document['rights']['end'])
        if convert_time_to_utc(new_end_date) != new_rights_date:
            return "End date in Rights in license document is difference with End date"

        # license: check updated in license old and new
        new_license_updated = convert_time_to_utc(new_license_document['updated'])
        old_license_updated = convert_time_to_utc(old_license_document['updated'])
        if new_license_updated <= old_license_updated \
                or new_license_updated != new_status_updated:
            return "License updated timestamp is not updated"

        return "Server response is 200"
    elif http_code >= 400 or http_code < 600:
        return "Server response is {}\n{}\n{}".format(str(http_code), response_value['type'], response_value['title'])
    else:
        return "Unknown response code"


def do_return(license_document, device_id, device_name):
    """
    Args:
        license_document (dict): License Document
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        str: Message of evaluation result about "request return".
    """
    try:
        status_document = get_status_document(license_document, device_id, device_name)

        # Need to wait for different timestamp between old status document(//updated/status/) and new one(same path)
        time.sleep(1)

        http_code, result = request_return(status_document, device_id, device_name)
        json_resp_data = json.loads(result)

        if 'status' in json_resp_data.keys():
            new_lic_str = request_license_document(json_resp_data)
            new_license = json.loads(new_lic_str)
        else:
            new_license = dict()

        return eval_return_result(http_code, json_resp_data,
                                  status_document,
                                  new_license, license_document)
    except Exception as e:
        return "Function: do_return\nMessage: " + '\n'.join(traceback.format_exception(Exception, e, None))


def request_return(status_document, device_id, device_name):
    """
    Args:
        status_document (dict): Status Document
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        int: http status code about server response.
        str: Server response value which is status document or error message.
    """
    return_link = generate_query(status_document['links']['return']['href'],
                                 device_id=device_id, device_name=device_name)
    method = 'PUT'
    url = urlparse(return_link)
    conn = http.client.HTTPConnection(url[1])
    conn.request(method, url[2] + '?' + url[4])

    with conn.getresponse() as result:
        return result.status, result.read().decode()


def eval_return_result(http_code, response_value, old_status_document,
                       new_license_document, old_license_document):
    """
    Args:
        http_code (int): Http status code about "request return".
        response_value (dict): Received message from server after "request return". It will be status document or error message.
        old_status_document (dict): Current Status Document before doing "request return"
        new_license_document (dict): Updated License Document after doing "request return"
        old_license_document (dict): Old License Document in epub file.

    Returns:
        str: Result message that describe correctly done of process or not, and new license document and status document is correctly renewal.
    """
    if http_code == 200:
        # check status in status document
        status_ready_to_cancelled = old_status_document['status'] == 'ready' \
                                    and response_value['status'] == 'cancelled'
        status_active_to_returned = old_status_document['status'] == 'active' \
                                    and response_value['status'] == 'returned'
        if not status_active_to_returned ^ status_ready_to_cancelled:
            return "Status in status document is not valid. before: {} current: {}".format(
                old_status_document['status'], response_value['status'])

        # check updated license timestamp in new status and new license
        old_updated_license = convert_time_to_utc(old_license_document['updated'])
        new_updated_license = convert_time_to_utc(new_license_document['updated'])
        new_updated_license_status = convert_time_to_utc(response_value['updated']['license'])
        if old_updated_license >= new_updated_license:
            return "Timestamp about license updated in lsd is not updated"

        if new_updated_license != new_updated_license_status:
            return "Timestamp about license updated in lcp is not updated"

        # check updated status timestamp in old status and new status
        old_updated_status_status = convert_time_to_utc(old_status_document['updated']['status'])
        new_updated_status_status = convert_time_to_utc(response_value['updated']['status'])
        if old_updated_status_status >= new_updated_status_status:
            return "Timestamp about status updated is not updated"

        return "Server response is 200"
    elif http_code >= 400 or http_code < 600:
        return "Server response is {} \n{} \n{}".format(str(http_code), response_value['type'], response_value['title'])
    else:
        return "Unknown response code"


def convert_time_to_utc(time_in_timezone):
    """
    Args:
        time_in_timezone (str): datetime in ISO 8601 format

    Returns:
        datetime: Converted datetime with timezone in UTC.
    """
    if time_in_timezone.find('Z') > 0:
        return datetime.strptime(time_in_timezone, "%Y-%m-%dT%H:%M:%SZ")
    else:
        tz_loc = time_in_timezone.find('+')
        if tz_loc == -1:
            tz_loc = time_in_timezone.find('-')
        new_time = datetime.strptime(time_in_timezone[:tz_loc], "%Y-%m-%dT%H:%M:%S")
        tz_delta = timedelta(hours=int(time_in_timezone[tz_loc + 1:tz_loc + 3]),
                             minutes=int(time_in_timezone[-2:]))
        if time_in_timezone[tz_loc] == '-':
            return new_time + tz_delta
        elif time_in_timezone[tz_loc] == '+':
            return new_time - tz_delta


def parse_arguments():
    """
    Returns:
        dict: System argument values -- epub_file, dev_id, instruction, end_date.
    """

    env = dict()
    env['epub_file'] = sys.argv[-1]

    for idx in range(len(sys.argv)):
        if sys.argv[idx] == '-i':
            env['instruction'] = sys.argv[idx + 1]
        elif sys.argv[idx] == '-d':
            env['dev_id'] = sys.argv[idx + 1]
        elif sys.argv[idx] == '-e':
            env['end_date'] = sys.argv[idx + 1]
        elif sys.argv[idx] == '-n':
            env['dev_name'] = sys.argv[idx + 1]

    return env


def get_license_document(epub_file_name):
    """
    Args:
        epub_file_name (str): Name or path of Epub file that has License Document(license.lcpl).

    Returns:
        dict: License Document from epub file
    """
    try:
        path = os.path.join(os.getcwd(), epub_file_name)
        with ZipFile(path) as zf:
            with zf.open('META-INF/license.lcpl') as license_document:
                return json.loads(license_document.read().decode(encoding='utf-8'))
    except Exception as e:
        return {"Function": "get_license_document",
                "Message": '\n'.join(traceback.format_exception(Exception, e, None))}


def get_status_document(license_document, device_id, device_name):
    """
    Args:
        license_document (dict): License document with link url for status document.
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        dict: Status document fetched from server.
    """
    status_link = license_document['links']['status']['href']
    status_link = status_link + "?id=" + device_id + "&name=" + device_name

    url = urlparse(status_link)
    req_path = url[2] + '?' + url[4]

    try:
        method = 'GET'
        conn = http.client.HTTPConnection(url[1])
        conn.request(method, req_path)

        with conn.getresponse() as result:
            return json.loads(result.read().decode())
    except Exception as e:
        return {"Function": "get_status_document",
                "Message": '\n'.join(traceback.format_exception(Exception, e, None))}


def fetch_status(status_document):
    # TODO: If you want to follow old lsd specification, you should use "old_json_schema_lsd.json" when call open function.
    """
    Args:
        status_document (dict): Dictionary object of status document.

    Returns:
        str: Result message of syntax check.
        bool: True or False by check result.
    """
    try:
        with open('json_schema_lsd.json') as schema_file:
            json_schema = json.loads(schema_file.read())
            json_validate(status_document, json_schema)

            return 'Syntax is correct.', True
    except exceptions.ValidationError:
        return 'Syntax is invalid.', False


def generate_query(template_url, device_id=None, device_name=None, end_date=None):
    """
    Args:
        template_url (str): Url string, has template query string. (e.g. <scheme>://<host>/<path>{?id,name})
        device_id (str): Device ID. default value: None
        device_name (str): Device name. default value: None
        end_date (str): Newly license expired date. It is optional. default value: None

    Returns:
        str: Url string. (e.g. <scheme>://<host>/<path>?id=device_id,name=device_name)
    """
    low_idx = template_url.find('{')
    high_idx = template_url.find('}')
    template_query = template_url[low_idx:high_idx + 1]

    query_str = str()
    if template_query[1] == '?':
        query_str += '?'
    keys = template_query[2:-1].split(',')
    for key in keys:
        if key == 'id' and device_id is not None:
            query_str += 'id=' + device_id + '&'
        elif key == 'name' and device_name is not None:
            query_str += 'name=' + device_name + '&'
        elif key == 'end' and end_date is not None:
            query_str += 'end=' + end_date + '&'

    if len(query_str) == 1:
        query_str = ""
    return template_url.replace(template_query, query_str[:-1])


def main():
    """

    """

    def usage():
        print("Usage: lsd_client.py [-option] [value] [Filename].epub")
        print("[option]")
        print("-i Interaction [fetch|fetch_license|register|renew|return]")
        print("-d Device id")
        print("-n Device name")
        print("-e ISO8601 end date")

    args = parse_arguments()

    if len(args) is not 4 and len(args) is not 5:
        usage()
        exit()

    license_document = get_license_document(args["epub_file"])
    if 'Function' in license_document.keys():
        print('Function: {}'.format(license_document['Function']))
        print('Message: {}'.format(license_document['Message']))
        exit()
    status_document = get_status_document(license_document, args["dev_id"], args["dev_name"])
    if 'title' in status_document.keys():
        print('Type: {}'.format(status_document['type']))
        print('Title: {}'.format(status_document['title']))
        exit()

    res, valid = fetch_status(status_document)

    if args["instruction"] == 'register':
        if valid:
            res += '\n' + do_register(license_document, args["dev_id"], args["dev_name"])
    elif args["instruction"] == 'renew':
        if valid:
            res += '\nregister: ' + do_register(license_document, args["dev_id"], args["dev_name"])
            res += '\n' + do_renew(license_document, args["end_date"], args["dev_id"], args["dev_name"])
    elif args["instruction"] == 'return':
        if valid:
            res += '\nregister: ' + do_register(license_document, args["dev_id"], args["dev_name"])
            res += '\n' + do_return(license_document, args["dev_id"], args["dev_name"])
    elif args["instruction"] == 'fetch_license':
        if valid:
            l = request_license_document(status_document)
            print(json.dumps(l, indent=4))
    elif args["instruction"] == 'fetch':
        if valid:
            print(json.dumps(status_document, indent=4))
            res += '\nStatus is ' + status_document['status']
    else:
        res = ""
        usage()

    print(Fore.GREEN + res)


if __name__ == "__main__":
    init()
    main()
