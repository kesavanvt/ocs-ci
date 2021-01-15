# -*- coding: utf8 -*-
"""
Module for interactions with Openshift Dedciated Cluster.

"""


import logging
import os
import json

from ocs_ci.framework import config
from ocs_ci.utility.utils import run_cmd, exec_cmd

logger = logging.getLogger(name=__file__)
openshift_dedicated = config.AUTH.get("openshiftdedicated", {})


def login():
    """
    Login to OCM client
    """
    token = openshift_dedicated["token"]
    cmd = f"ocm login --token={token} --url=staging"
    logger.info("Logging in to OCM cli")
    run_cmd(cmd, secrets=[token])
    logger.info("Successfully logged in to OCM")


def create_cluster(cluster_name):
    """
    Create OCP cluster.

    Args:
        cluster_name (str): Cluster name.

    """
    configs = config.ENV_DATA["configs"]
    cmd = f"osde2e test --configs {configs}"
    exec_cmd(cmd, timeout=7200)


def get_cluster_details(cluster):
    """
    Returns info about the cluster which is taken from the OCM command.

    Args:
        cluster (str): Cluster name.

    """
    cmd = f"ocm describe cluster {cluster} --json=true"
    out = run_cmd(cmd)
    return json.loads(out)


def get_kubeconfig(cluster, path):
    """
    Export kubeconfig to provided path.

    Args:
        cluster (str): Cluster name.
        path (str): Path where to create kubeconfig file.

    """
    path = os.path.expanduser(path)
    basepath = os.path.dirname(path)
    os.makedirs(basepath, exist_ok=True)
    cluster_details = get_cluster_details(cluster)
    cluster_id = cluster_details.get("id")
    cmd = f"ocm get /api/clusters_mgmt/v1/clusters/{cluster_id}/credentials"
    out = run_cmd(cmd)
    credentials = json.loads(out)
    with open(path, "w+") as fd:
        fd.write(credentials.get("kubeconfig"))


def destroy_cluster(cluster):
    """
    Destroy the cluster on Openshift Dedicated.

    Args:
        cluster (str): Cluster name or ID.

    """
    cluster_details = get_cluster_details(cluster)
    cluster_id = cluster_details.get("id")
    cmd = f"ocm delete /api/clusters_mgmt/v1/clusters/{cluster_id}"
    run_cmd(cmd)


def list_cluster():
    """
    Returns info about the openshift dedciated clusters which is taken from the OCM command.

    """
    cmd = "ocm list clusters --columns name,state"
    out = run_cmd(cmd)
    result = out.strip().split("\n")
    cluster_list = []
    for each_line in result[1:]:
        name, state = each_line.split()
        cluster_list.append([name, state])
    return cluster_list
