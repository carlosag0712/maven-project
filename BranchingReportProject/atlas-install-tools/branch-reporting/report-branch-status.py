#!/usr/bin/env python
import argparse

import os
from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth

from functools import partial

from terminaltables import AsciiTable
from multiprocessing.dummy import Pool as ThreadPool
from termcolor import colored

import urllib3

FETCH_ERROR = "FETCH ERROR"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def results_to_list(headers=[], results=[]):
    result = [headers]
    for r in results:
        record = []
        for h in headers:
            record.append(r.get(h))
        result.append(record)
    return result


class JenkinsClient():
    def __init__(self, host, user, token):
        self.url_template = "https://{host}/job/{dir}/job/{repo}/job/{branch}/lastBuild/api/json"

        self.host = host
        self.auth = HTTPBasicAuth(user, token)

    def _build_url(self, directory, repo, branch):
        _dir = directory.replace('/', '/job/')
        return self.url_template.format(host=self.host, repo=repo, dir=_dir, branch=branch.replace('/', '%2F'))

    def _get_data(self, url):
        r = requests.get(url, auth=self.auth, verify=False)
        if r.status_code != 200:
            print("error fetching %s" % url)
            print(r.text)
            return {"job_url": url, "result": FETCH_ERROR}
        else:
            data = r.json()
            return {
                "job_url": data["url"]
                , "duration": "{round(data['duration']/1000)} sec." if "duration" in data else "0s"
                , "job_name": data["fullDisplayName"]
                , "result": data["result"]
                , "is_building": data["building"]
                , "timestamp": datetime.fromtimestamp(data["timestamp"]/1000).strftime(
                    '%Y-%m-%d %H:%M:%S') if "timestamp" in data else "--"
            }

    def status(self, directory, repo, branch):
        url = self._build_url(directory, repo, branch)
        data = self._get_data(url)
        return data


def get_args(args=None):
    parser = argparse.ArgumentParser(description="branch status reporting")
    parser.add_argument('-j', '--jenkins-host', default="jenkins.corp.ad.ctc")
    parser.add_argument('-u', '--user', default="ATLAS_JENKINS_USER")
    parser.add_argument('-t', '--token', default="ATLAS_JENKINS_USER_TOKEN")
    parser.add_argument('-r', '--repo-file', default="repolist.txt")
    parser.add_argument('-d', '--dir', default="Digital/CTC/ATLAS")
    parser.add_argument('-b', '--branch')
    return parser.parse_args(args=args)


def read_repos(file_name):
    with open(file_name, "r") as f_:
        result = [l.strip() for l in f_.readlines()]
    return list(filter(lambda l: l, result))


def get_data(host, user, token, directory, branch, repo):
    client = JenkinsClient(host, user, token)
    return client.status(directory, repo, branch)


def retrieve_statuses(fetch_function, repos, maxdop=0):
    effectve_maxdop = len(repos) if maxdop == 0 else maxdop
    pool = ThreadPool(effectve_maxdop if effectve_maxdop > 1 else 1)
    statuses = pool.map(fetch_function, repos)
    return statuses


def colorize(to_list):
    new_list = []
    for record in to_list:
        new_record = []
        for element in record:
            if "SUCCESS" in str(element).upper():
                new_record.append(colored(element, 'green'))
            elif "FAILURE" in str(element).upper():
                new_record.append(colored(element, 'red'))
            elif "UNSTABLE" in str(element).upper():
                new_record.append(colored(element, 'yellow'))
            elif FETCH_ERROR in str(element).upper():
                new_record.append(colored(element, 'red'))
            else:
                new_record.append(element)
        new_list.append(new_record)
    return new_list


def build_table(title, statuses, attributes):
    to_list = results_to_list(attributes, statuses)
    to_list = colorize(to_list)
    table = AsciiTable(to_list)
    table.title = title
    table.inner_row_border = True
    return table.table


if __name__ == "__main__":
    params = get_args()

    fetch_function = partial(get_data, params.jenkins_host, params.user, params.token, params.dir,
                             params.branch)

    repos = read_repos(params.repo_file)

    statuses = retrieve_statuses(fetch_function, repos)

    query_attributes = ["job_name", "job_url", "result", "duration", "is_building", "timestamp"]
    table = build_table("Job Statuses. Branch: %s" % params.branch, statuses, query_attributes)

    print(table)
