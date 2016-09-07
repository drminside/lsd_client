# -*- coding: utf-8 -*-

"""
Name: LSD Virtual client for server test
File Name: lsd_client.py
version: 1.0
History
    Created by Ahram Oh(aroh@drminside.com) in 06.27.2016 v0.1
    Update script reference by LSD specification by Ahram Oh(aroh@drminside.com) in 09.08.2016 v1.0
Tools: PyCharm 2016.2.2 (JetBrain, IDE)
Dependency: pytz
Prerequisites: epub files that makes by LCP server with LSD (Server must have status document associated by epub files)
Detail: LSD Virtual client for server test is test script for LCP server with LSD.
    Usage
    1. Create test material from server. This test material must be inserted in database with device id and device name.
    2. In this script, change the "dev_name" variable to device name on step 1.
    2. Type command. e.g. $ python lsd_client.py -i register -d devtest test.epub
    3. You can see test result text in terminal.
"""

import traceback
import pip
import importlib
import sys
import os
import json
import http.client

from urllib.parse import urlparse, quote
from datetime import datetime, timedelta
from zipfile import ZipFile

if importlib.util.find_spec('pytz') is None:
    pip.main(['install', 'pytz'])
timezone = importlib.import_module(name='pytz').timezone

dev_name = "devComputer"


def request_license_document(status_document):
    """
    Args:
        status_document (dict): It has url information for request license document to server.

    Returns:
        str: Message that based on http status code.
        str: License document that received from server.
    """
    try:
        license_link = status_document['links']['license']['href']

        url = urlparse(license_link)
        conn = http.client.HTTPConnection(url[1])
        conn.request('GET', url[2])

        with conn.getresponse() as result:
            if result.status == 200:
                return "Server response is 200", result.read().decode()
            else:
                return "Server response error", ""
    except Exception as e:
        return "Function: get_status\nMessage: " + '\n'.join(traceback.format_exception(Exception, e, None)), ""


def do_register(license_document, device_id, device_name):
    """
    Args:
        license_document (dict): Dictionary object that has license document information from epub file, It extracted before task of "request register".
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        str: Message of evaluation result about "request register".
    """
    try:
        status_document = get_status_document(license_document, device_id, device_name)
        if status_document['status'] != 'ready':
            return "do_register: License is not ready."

        code, response_data = request_register(status_document, device_id, device_name)
        return eval_register_result(code, status_document, json.loads(response_data))
    except Exception as e:
        return "Function: get_status\nMessage: " + '\n'.join(traceback.format_exception(Exception, e, None))


def request_register(status_document, device_id, device_name):
    """
    Args:
        status_document (dict): Dictionary object that has status document information from server. It received before task of "request register".
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        int: Http status code about server response.
        str: Server response value. It has different value(status document or error message) by http status code.
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
        http_code (int): Http status code about server response in "request register".
        old_status_document (dict): Status document object it received from server when before task of "request register".
        response_value (dict): The given value from server that after task of "request register". It is status document when http_code is 200, or error message If http_code has another value.

    Returns:
        str: Evaluation result message. This message describe followings, server did normally process about request, license, and status document from server are correctly renewal.
    """
    if http_code == 200:
        result_message = "Server response is 200"
        new_updated_status_time = convert_time_to_utc(response_value['updated']['status'])
        old_updated_status_time = convert_time_to_utc(old_status_document['updated']['status'])

        if response_value['status'] != 'active' or new_updated_status_time <= old_updated_status_time:
            result_message += "\nWrong response received."

        return result_message
    elif http_code == 400 or http_code >= 500 or http_code < 600:
        return "Server response is " + str(http_code) + "\n" + response_value['type'] + '\n' + response_value['title']
    else:
        return "Unknown response code."


def do_renew(license_document, end_date, device_id, device_name):
    """
    Args:
        license_document (dict): Dictionary object, contains license document from epub file.
        end_date (str): License expired date, you want renewal.
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        str: Message of evaluation result about "request renew".
    """
    try:
        status_document = get_status_document(license_document, device_id, device_name)
        if status_document['status'] != 'active':
            return "do_renew: License is not registration."
        # check validation using exception handler
        convert_time_to_utc(end_date)

        http_code, result = request_renew(status_document, end_date, device_id=device_id, device_name=device_name)
        json_resp_data = json.loads(result)

        if 'status' in json_resp_data.keys():
            _, new_lic_str = request_license_document(json_resp_data)
            new_license = json.loads(new_lic_str)
        else:
            new_license = ""

        return eval_renew_result(http_code, json_resp_data, status_document, new_license, license_document, end_date)

    except Exception as e:
        return "Function: get_status\nMessage: " + '\n'.join(traceback.format_exception(Exception, e, None))


def request_renew(status_document, end_date, device_id, device_name):
    """
    Args:
        status_document (dict): Dictionary object, contains status document information.
        end_date (str): License expired date, you want renewal.
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        int: Http status code about server response
        str: Server response message. It has different value(status document or error message) by http status code.
    """
    if end_date is None:
        raise RuntimeError("end_date is None")

    renew_object = status_document['links']['renew']
    renew_link = str()
    for renew in renew_object:
        if 'type' in renew and renew['type'] == "application/vnd.readium.lcp.license-1.0+json":
            renew_link = renew['href']

    renew_link = generate_query(renew_link, device_id=device_id, device_name=device_name,
                                end_date=quote(end_date))
    method = 'PUT'
    url = urlparse(renew_link)
    conn = http.client.HTTPConnection(url[1])
    conn.request(method, url[2] + '?' + url[4])

    with conn.getresponse() as result:
        return result.status, result.read().decode()


def eval_renew_result(http_code, response_value, old_status_document, new_license_document, old_license_document,
                      new_end_date):
    """
    Args:
        http_code (int): http status code about "request renew".
        response_value (dict): Response value, either new status document or error message structed json.
        old_status_document (dict): Status document received from server, before task of "request renew".
        new_license_document (dict): New license document received from server.
        old_license_document (dict): License document from epub file, before task of "request renew".
        new_end_date (str): Newly expired date of license, written by user.

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
        if new_license_updated <= old_license_updated or new_license_updated != new_status_updated:
            return "License updated timestamp is not updated"

        return "Server response is 200"
    elif http_code >= 400 or http_code < 600:
        return "Server response is " + str(http_code) + "\n" + response_value['type'] + '\n' + response_value['title']
    else:
        return "Unknown response code"


def do_return(license_document, device_id, device_name):
    """
    Args:
        license_document (dict): Dictionary object, contains license document information.
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        str: Message of evaluation result about "request return".
    """
    try:
        status = get_status_document(license_document, device_id, device_name)
        http_code, result = request_return(status, device_id, device_name)
        json_resp_data = json.loads(result)

        if 'status' in json_resp_data.keys():
            _, new_lic_str = request_license_document(json_resp_data)
            new_license = json.loads(new_lic_str)
        else:
            new_license = dict()

        return eval_return_result(http_code, json_resp_data, status, new_license, license_document)
    except Exception as e:
        return "Function: get_status\nMessage: " + '\n'.join(traceback.format_exception(Exception, e, None))


def request_return(status_document, device_id, device_name):
    """
    Args:
        status_document (dict): Dictionary object, contains status document information
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        int: http status code about server response.
        str: Server response value. It has different value(status document or error message) by http status code.
    """
    return_link = generate_query(status_document['links']['return']['href'],
                                 device_id=device_id, device_name=device_name)
    method = 'PUT'
    url = urlparse(return_link)
    conn = http.client.HTTPConnection(url[1])
    conn.request(method, url[2] + '?' + url[4])

    with conn.getresponse() as result:
        return result.status, result.read().decode()


def eval_return_result(http_code, response_value, old_status_document, new_license_document, old_license_document):
    """
    Args:
        http_code (int): Http status code about "request return".
        response_value (dict): Received message from server after "request return". It will be status document or error message.
        old_status_document (dict): Status document that received before task of "request return" from server.
        new_license_document (dict): License document that received after task of "request return" from server.
        old_license_document (dict): License document that takes in epub file.

    Returns:
        str: Result message that describe correctly done of process or not, and new license document and status document is correctly renewal.
    """
    if http_code == 200:
        # check status in status document
        status_ready_to_cancelled = old_status_document['status'] == 'ready' and response_value['status'] == 'cancelled'
        status_active_to_returned = old_status_document['status'] == 'active' and response_value['status'] == 'returned'
        if not status_active_to_returned ^ status_ready_to_cancelled:
            return "Status in status document is not valid." + \
                   " before: " + old_status_document['status'] + " current: " + response_value['status']

        # check updated license timestamp in new status and new license
        old_updated_license = convert_time_to_utc(old_license_document['updated'])
        new_updated_license = convert_time_to_utc(new_license_document['updated'])
        new_updated_license_status = convert_time_to_utc(response_value['updated']['license'])
        if old_updated_license >= new_updated_license or new_updated_license != new_updated_license_status:
            return "Timestamp about license updated is not updated"

        # check updated status timestamp in old status and new status
        old_updated_status_status = convert_time_to_utc(old_status_document['updated']['status'])
        new_updated_status_status = convert_time_to_utc(response_value['updated']['status'])
        if old_updated_status_status >= new_updated_status_status:
            return "Timestamp about license updated is not updated"

        return "Server response is 200"
    elif http_code >= 400 or http_code < 600:
        return "Server response is " + str(http_code) + "\n" + response_value['type'] + '\n' + response_value['title']
    else:
        return "Unknown response code"


def convert_time_to_utc(time_in_timezone):
    """
    Args:
        time_in_timezone (str): Formed string value of datetime by ISO 8601 standards.

    Returns:
        datetime: Changed datetime object from timezone in UTC.
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


def init_client():
    """
    Returns:
        dict: System argument values -- epub_file, dev_id, instruction, end_date.
    """
    epub_file = sys.argv[-1]
    argv_instruction = str()
    argv_dev_id = str()
    argv_end_date = str()
    for idx in range(len(sys.argv)):
        if sys.argv[idx] == '-i':
            argv_instruction = sys.argv[idx + 1]
        if sys.argv[idx] == '-d':
            argv_dev_id = sys.argv[idx + 1]
        if sys.argv[idx] == '-end':
            argv_end_date = sys.argv[idx + 1]

    env = {"epub_file": epub_file, "dev_id": argv_dev_id, "instruction": argv_instruction, "end_date": argv_end_date}
    return env


def get_license_document(epub_file_name):
    """
    Args:
        epub_file_name (str): Name or path of Epub file that has license document(license.lcpl).

    Returns:
        dict: Dictionary object of license document from epub file
    """
    try:
        path = os.path.join(os.getcwd(), epub_file_name)
        with ZipFile(path) as zf:
            with zf.open('META-INF/license.lcpl') as license_document:
                return json.loads(license_document.read().decode(encoding='utf-8'))
    except Exception as e:
        return {"Function": "get_license", "Message": '\n'.join(traceback.format_exception(Exception, e, None))}


def get_status_document(license_document, device_id, device_name):
    """
    Args:
        license_document (dict): License document, has url of status document associated by license id.
        device_id (str): Device ID
        device_name (str): Device name

    Returns:
        dict: Dictionary object of status document from server.
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
        return {"Function": "get_status", "Message": '\n'.join(traceback.format_exception(Exception, e, None))}


def fetch_status(status_document):
    # TODO: If client needs to check a validation about status document more details, this script must be modify.
    """
    Args:
        status_document (dict): Dictionary object of status document.

    Returns:
        str: Result message of syntax check.
        bool: True or False by check result.
    """
    root = ['id', 'status', 'links', 'updated']
    links = ['license', 'register', 'return', 'renew']
    updated = ['license', 'status']

    for k in status_document:
        if k not in root:
            return 'Syntax is incorrect.', False

    for k in status_document['links']:
        if k not in links:
            return 'Syntax is incorrect.', False

    for k in status_document['updated']:
        if k not in updated:
            return 'Syntax is incorrect.', False

    if 'href' not in status_document['links']['license']:
        return 'Syntax is incorrect.', False
    if 'href' not in status_document['links']['register']:
        return 'Syntax is incorrect.', False
    if 'href' not in status_document['links']['return']:
        return 'Syntax is incorrect.', False
    if 'href' not in status_document['links']['renew'][1]:
        return 'Syntax is incorrect.', False

    return 'Syntax is correct.', True


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


def lsd_test_client():
    """

    """

    def usage():
        print("Usage: lsd_client.py [-option] [value] epub_file")
        print("[option]")
        print("-i instruction {'fetch'|'activation'|'renew'|'return'}")
        print("-d device id")
        print("-end end date when it used renew instruction. ISO8601 format")

    if len(sys.argv) < 5:
        usage()
        exit()

    args = init_client()

    license_document = get_license_document(args["epub_file"])
    if 'Function' in license_document.keys():
        print('Function: ' + license_document['Function'])
        print('Message: ' + license_document['Message'])
        exit()
    status_document = get_status_document(license_document, args["dev_id"], dev_name)
    if 'status' not in status_document.keys():
        print('Function: ' + status_document['Function'])
        print('Message: ' + status_document['Message'])
        exit()
    res, valid = fetch_status(status_document)

    if args["instruction"] == 'register':
        if valid:
            res += '\n' + do_register(license_document, args["dev_id"], dev_name)
    elif args["instruction"] == 'renew':
        if valid:
            res += '\nregister: ' + do_register(license_document, args["dev_id"], dev_name) + ' register for renew'
            res += '\n' + do_renew(license_document, args["end_date"], args["dev_id"], dev_name)
    elif args["instruction"] == 'return':
        if valid:
            res += '\nActivation: ' + do_register(license_document, args["dev_id"], dev_name) + ' register for return'
            res += '\n' + do_return(license_document, args["dev_id"], dev_name)
    elif args["instruction"] == 'license':
        if valid:
            msg, l = request_license_document(status_document)
            res += '\nLicense request: ' + msg
    elif args["instruction"] == 'fetch':
        if valid:
            res += '\nStatus is ' + status_document['status']
    else:
        res = ""
        usage()

    print(res)


if __name__ == "__main__":
    lsd_test_client()
