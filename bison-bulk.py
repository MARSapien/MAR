import os
import csv
import yaml
import argparse

from pyfiglet import Figlet
from typing import Dict, List
from requests import Response

import requests
import json

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# need to sort first

ap = argparse.ArgumentParser()
ap.add_argument("-e", "--name", required=True, help="name of the environment - win|dev|prd")
ap.add_argument("-f", "--file", required=True, help="file name contains hostname with header 'Node'")
ap.add_argument("-a", "--action", required=True, help="insert|delete")
args = vars(ap.parse_args())

environments = ["dev","acc","prd"]

if args["name"] in environments:
    bo_env = args["name"]
else:
    print("ndc-api environment is undefined or wrongly defined")
    quit()

operations = ["insert","delete","update"]

if args["action"] in operations:
    action = args["action"]
else:
    print("bison bulk operation is undefined or wrongly defined")
    quit()

with open(os.getcwd()+"/config.yml", 'r') as yconf:
    cfg = yaml.load(yconf, Loader=yaml.FullLoader)

infile = os.path.join(args["file"])
outfile = os.path.join('output.csv')

BISON_API_URL = cfg[bo_env]["BISON_API_URL"]

# 1. device name must be in FQDN format
# 2. File format is CSV
# 3. File must contain header 'Node'

def _request(method=None, url=None, json=None, data=None) -> Response:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {accessToken}",
        "Sec-Fetch-Mode": "cors",
        "Content-Type": "application/json"
    }

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=json,
        data=data,
        verify=False
    )

    status_code = response.status_code
    if status_code != 200:
        if status_code == 400:
            print(f"Request Error:{status_code}: Bad request")
        elif status_code == 403:
            print(f"Request Error:{status_code}: Your access token has expired")
        else:
            print(f"Request Error:{status_code}: Error code")

    return response

def _get(url, json=None) -> Response:
    return _request(method="GET", url=url, json=json)

def _post(url, json=None) -> Response:
    return _request(method="POST", url=url, json=json)

def _put(url, json=None) -> Response:
    return _request(method="PUT", url=url, json=json)

def _delete(url, json=None) -> Response:
    return _request(method="DELETE", url=url, json=json)

def getNodeId(host) -> str:
    url = BISON_API_URL + "nodes/name/" + host
    response = _get(url)

    result = json.loads(response.content.decode('utf-8'))

    if int(result['totalElements']) == 1:
        return json.loads(response.text)['content'][0]['id']
    else:
        print(f"node {{{host}}} not exists")
        return ""

def getNodeRoutes(nodeId) -> Dict:
    url = BISON_API_URL + f"routes/{nodeId}"
    response = _get(url)
    return json.loads(response.content.decode('utf-8'))

def readNodeList(file) -> List[str]:
    with open(file) as csvfile:
        reader = csv.DictReader(csvfile)
        nodeList = [ row["Node"] for row in reader if row['Node'].strip() ]
    return nodeList

def tokenCookie():
    cookieToken = input("Paste your token cookie (Bearer XYZ) without quotes from web debugger: ")
    if cookieToken[0:7] == "Bearer ":
        cookieToken = cookieToken[7:]
    return cookieToken

def bulkInsert():
    nodeList = readNodeList(infile)
    for node in nodeList:
        host = node.upper()

        data = { 'name': host }
        insertUrl = BISON_API_URL + "nodes"
        insertResponse = _post(insertUrl, json=data)

        print(f"node={host}, insert status={insertResponse.status_code}")

def bulkDelete():
    nodeList = readNodeList(infile)
    for node in nodeList:
        host = node.lower()

        nodeId = getNodeId(host)
        if not nodeId:
            continue

        delUrl = BISON_API_URL + f"nodes/{nodeId}"
        delResponse = _delete(delUrl)
        print(f"node={host}, id={nodeId}, delete status={delResponse.status_code}")

def bulkUpdateAsg(assignment_group: str) -> None:
    nodeList = readNodeList(infile)
    for node in nodeList:
        host = node.lower()

        nodeId = getNodeId(host)
        if not nodeId:
            continue

        routeList = getNodeRoutes(nodeId)
        routeIdList = [ str(route["Id"]) for route in routeList ]
        data = { 'AssignmentGroup': assignment_group }

        for routeId in routeIdList:
            asgUrl = BISON_API_URL + f"routes/assignment-group/{routeId}"
            asgResponse = _put(asgUrl, json=data)

            print(f"node={host}, new assignment group={assignment_group}, update status={asgResponse.status_code}")

def bulkUpdate(severity: str, pmtsInt: str, impact: str, urgency: str) -> None:
    nodeList = readNodeList(infile)
    for node in nodeList:
        host = node.lower()

        nodeId = getNodeId(host)
        if not nodeId:
            continue

        routeList = getNodeRoutes(nodeId)
        routeIdList = [ route["Id"] for route in routeList ]

        data = {
            'Severity': severity,
            'PmtsInterface': pmtsInt,
            'Impact': impact,
            'Urgency': urgency
        }
        for routeId in routeIdList:
            urgUrl = BISON_API_URL + f"routes/severity/{routeId}"
            urgResponse = _put(urgUrl, json=data)
            print(f"node={host}, severity={severity}, update status={urgResponse.status_code}")

def bulkUpdateSync(autosync: str) -> None:
    nodeList = readNodeList(infile)
    for node in nodeList:
        host = node.lower()

        nodeId = getNodeId(host)
        if not nodeId:
            continue

        data = { 'resetFlag': autosync.upper() }
        syncUrl = BISON_API_URL + f"nodes/sync/{nodeId}"
        syncResponse = _put(syncUrl, json=data)
        print(f"node={host}, autosync flag={autosync}, update status={syncResponse.status_code}")

def bulkUpdateClsService(classification_service: str) -> None:
    nodeList = readNodeList(infile)
    for node in nodeList:
        host = node.lower()

        nodeId = getNodeId(host)
        if not nodeId:
            continue

        routeList = getNodeRoutes(nodeId)
        routeIdList = [ route["Id"] for route in routeList ]

        data = { 'ClassificationService': classification_service }
        for routeId in routeIdList:
            url = BISON_API_URL + f"routes/classification-service/{routeId}"
            response = _put(url, json=data)
            print(f"node={host}, new classification service={classification_service}, update status={response.status_code}")

def selectionPrompt(
    item_name: str,
    item_list: List[str],
    item_values: List[str]=[],
    return_index: bool=False,
    ):
    itemSelectionString = "".join([ f"\n\t({i+1}): {item}" for i,item in enumerate(item_list) ])
    itemSelectionReprompt = ", ".join([ f"({i+1}): {item} " for i,item in enumerate(item_list) ])
    while True:
        userInput = input(f"\nChoose {item_name} below:{itemSelectionString}\nEnter your choice: ")
        if not userInput in [ str(i) for i in range(1,len(item_list)+1) ]:
            print(f"Accepted values - {itemSelectionReprompt}")
            continue
        else:
            break

    if not return_index:
        userInput = int(userInput)-1
        return item_list[userInput] if len(item_values) == 0 else item_values[userInput]
    else:
        return userInput

if __name__ == '__main__':
    accessToken = tokenCookie()

    f = Figlet(font='slant')
    print(f.renderText('Bison Bulk'))

    if action == "insert":
        bulkInsert()

    elif action == "delete":
        bulkDelete()

    elif action == "update":
        updateList = [
            "Assignment Group",
            "Classification Service",
            "Severity",
            "Autosync",
        ]
        updateType = selectionPrompt("the options", updateList)

        if updateType == "Assignment Group":
            print("Update Assignment Group is selected")
            newAsg = input("Paste valid new assignment group: ")
            #TODO pull list ASG from SNOW
            bulkUpdateAsg(newAsg)

        if updateType == "Classification Service":
            print("Update Classification Service is selected")
            newClsService = input("Paste valid new classification service: ")
            bulkUpdateClsService(newClsService)

        elif updateType == "Severity":
            print("Update Severity is selected")

            severityList = [
                "Critical",
                "Major",
                "Minor",
                "Warning",
                "Normal",
            ]
            severity = selectionPrompt("severity", severityList)

            pmtsIntList = [
                "Call ticket",
                "Manual only",
                "Notify only",
            ]
            pmtsInt = selectionPrompt("pmts interface", pmtsIntList)

            impactList = [
                "1 - High",
                "2 - Medium",
                "3 - Low",
            ]
            impact = selectionPrompt("impact", impactList)

            urgencyList = [
                "1 - High",
                "2 - Medium",
                "3 - Low",
            ]
            urgency = selectionPrompt("urgency", urgencyList)

            bulkUpdate(severity, pmtsInt, impact, urgency)

        elif updateType == "Autosync":
            print("Update Autosync is selected")

            autosyncList = [
                "True (Disable Autosync)",
                "False (Enable Autosync)",
            ]
            autosyncValue = [
                "T",
                "F",
            ]
            autosync = selectionPrompt("autosync", autosyncList, autosyncValue)

            bulkUpdateSync(autosync)

    # debugging purpose
    print(f"\nSummary:\n\tenvironment: {bo_env}\n\taction: {action}\n\tfile: {infile}")
