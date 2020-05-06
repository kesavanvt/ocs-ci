import logging
from concurrent.futures import ThreadPoolExecutor

from ocs_ci.framework.testlib import ignore_leftovers
from ocs_ci.ocs import constants
from ocs_ci.ocs.resources.pvc import delete_pvcs
from tests import helpers

log = logging.getLogger(__name__)


def pods_creation(pod_factory, pvc_objs):
    """
    Create pods

    Args:
        pvc_objs (list): List of ocs_ci.ocs.resources.pvc.PVC instances
        pvc_objs (function): Function to be used for creating pods

    Returns:
        list: list of Pod objects
    """
    pod_objs = []

    # Create one pod using each RWO PVC and two pods using each RWX PVC
    for pvc_obj in pvc_objs:
        if pvc_obj.volume_mode == 'Block':
            pod_dict = constants.CSI_RBD_RAW_BLOCK_POD_YAML
            raw_block_pv = True
        else:
            raw_block_pv = False
            pod_dict = ''
        if pvc_obj.access_mode == constants.ACCESS_MODE_RWX:
            pod_obj = pod_factory(
                interface=pvc_obj.interface, pvc=pvc_obj, status="",
                pod_dict_path=pod_dict, raw_block_pv=raw_block_pv
            )
            pod_objs.append(pod_obj)
        pod_obj = pod_factory(
            interface=pvc_obj.interface, pvc=pvc_obj, status="",
            pod_dict_path=pod_dict, raw_block_pv=raw_block_pv
        )
        pod_objs.append(pod_obj)

    return pod_objs


def create_pvcs(
    multi_pvc_factory, interface, project=None, status="", storageclass=None
):
    pvc_num = 1
    pvc_size = 5

    if interface == 'CephBlockPool':
        access_modes = [
            'ReadWriteOnce',
            'ReadWriteOnce-Block',
            'ReadWriteMany-Block']
    else:
        access_modes = ['ReadWriteOnce', 'ReadWriteMany']
    # Create pvcs
    pvc_objs = multi_pvc_factory(
        interface=interface,
        project=project,
        storageclass=storageclass,
        size=pvc_size,
        access_modes=access_modes,
        access_modes_selection='distribute_random',
        status=status,
        num_of_pvc=pvc_num,
        wait_each=False,
        timeout=360
    )

    for pvc_obj in pvc_objs:
        pvc_obj.interface = interface

    return pvc_objs


def delete_pods(pod_objs):
    """
    Delete pods
    """
    for pod_obj in pod_objs:
        pod_obj.delete()
    return True


@ignore_leftovers
def test_create_delete_pvcs(multi_pvc_factory, pod_factory, project=None):
    # create the pods for deleting
    # Create rbd pvcs for pods
    pvc_objs_rbd = create_pvcs(
        multi_pvc_factory,
        'CephBlockPool',
        project=project)
    storageclass_rbd = pvc_objs_rbd[0].storageclass

    # Create cephfs pvcs for pods
    pvc_objs_cephfs = create_pvcs(
        multi_pvc_factory, 'CephFileSystem', project=project
    )
    storageclass_cephfs = pvc_objs_cephfs[0].storageclass

    all_pvc_for_pods = pvc_objs_rbd + pvc_objs_cephfs
    # Check pvc status
    for pvc_obj in all_pvc_for_pods:
        helpers.wait_for_resource_state(
            resource=pvc_obj, state=constants.STATUS_BOUND, timeout=1200  # Timeout given 5 minutes
        )
        pvc_info = pvc_obj.get()
        setattr(pvc_obj, 'volume_mode', pvc_info['spec']['volumeMode'])

    # Create pods
    pods_to_delete = pods_creation(pod_factory, all_pvc_for_pods)
    for pod_obj in pods_to_delete:
        helpers.wait_for_resource_state(
            resource=pod_obj, state=constants.STATUS_RUNNING, timeout=300  # Timeout given 5 minutes
        )

    logging.info(f"#### Created the pods for deletion later...pods = {pods_to_delete}")
    # Create PVCs for deleting
    # Create rbd pvcs for deleting
    pvc_objs_rbd = create_pvcs(
        multi_pvc_factory=multi_pvc_factory, interface='CephBlockPool',
        project=project, status="", storageclass=storageclass_rbd
    )

    # Create cephfs pvcs for deleting
    pvc_objs_cephfs = create_pvcs(
        multi_pvc_factory=multi_pvc_factory, interface='CephFileSystem',
        project=project, status="", storageclass=storageclass_cephfs
    )

    all_pvc_to_delete = pvc_objs_rbd + pvc_objs_cephfs
    # Check pvc status
    for pvc_obj in all_pvc_to_delete:
        helpers.wait_for_resource_state(
            resource=pvc_obj, state=constants.STATUS_BOUND, timeout=300  # Timeout given 5 minutes
        )

    logging.info(f"#### Created the PVCs for deletion later...PVCs={all_pvc_to_delete}")

    # Create PVCs for new pods
    pvc_objs_rbd = create_pvcs(
        multi_pvc_factory=multi_pvc_factory, interface='CephBlockPool',
        project=project, status="", storageclass=storageclass_rbd
    )

    # Create cephfs pvcs for new pods # for deleting
    pvc_objs_cephfs = create_pvcs(
        multi_pvc_factory=multi_pvc_factory, interface='CephFileSystem',
        project=project, status="", storageclass=storageclass_cephfs
    )

    all_pvc_for_new_pods = pvc_objs_rbd + pvc_objs_cephfs
    # Check pvc status
    for pvc_obj in all_pvc_for_new_pods:
        helpers.wait_for_resource_state(
            resource=pvc_obj, state=constants.STATUS_BOUND, timeout=300  # Timeout given 5 minutes
        )
        pvc_info = pvc_obj.get()
        setattr(pvc_obj, 'volume_mode', pvc_info['spec']['volumeMode'])

    logging.info(f"#### Created the PVCs required for creating New Pods...{all_pvc_for_new_pods}")

    executor = ThreadPoolExecutor(max_workers=10)
    # Start creating new PVCs
    # Start creating rbd PVCs
    rbd_pvc_exeuter = executor.submit(
        create_pvcs, multi_pvc_factory=multi_pvc_factory,
        interface='CephBlockPool', project=project, status="",
        storageclass=storageclass_rbd
    )

    logging.info("#### Started creating new RBD PVCs in thread...")
    # Start creating cephfs pvc
    cephfs_pvc_exeuter = executor.submit(
        create_pvcs, multi_pvc_factory=multi_pvc_factory,
        interface='CephFileSystem', project=project,
        status="", storageclass=storageclass_cephfs
    )

    logging.info("#### Started creating new cephfs PVCs in thread...")
    # Start creating pods
    pods_create_executer = executor.submit(
        pods_creation, pod_factory, all_pvc_for_new_pods
    )

    # Start deleting pods
    pods_delete_executer = executor.submit(delete_pods, pods_to_delete)
    logging.info(f"### Started deleting the pods_to_delete = {pods_to_delete}")

    # Start deleting PVC
    pvc_delete_executer = executor.submit(delete_pvcs, all_pvc_to_delete)
    logging.info(f"### Started deleting the all_pvc_to_delete = {all_pvc_to_delete}")

    log.info(
        "These process are started: Bulk delete PVC, Pods. Bulk create PVC, "
        "Pods. Waiting for its completion"
    )

    from time import sleep
    while not (rbd_pvc_exeuter.done() and cephfs_pvc_exeuter.done() and pods_create_executer.done()
               and pods_delete_executer.done() and pvc_delete_executer.done()):
        sleep(10)
        logging.info(
            "#### create_delete_pvcs....Waiting for threads to complete...")

    new_rbd_pvcs = rbd_pvc_exeuter.result()
    new_cephfs_pvcs = cephfs_pvc_exeuter.result()
    new_pods = pods_create_executer.result()

    # Check pvc status
    for pvc_obj in new_rbd_pvcs + new_cephfs_pvcs:
        helpers.wait_for_resource_state(
            resource=pvc_obj, state=constants.STATUS_BOUND, timeout=300  # Timeout given 5 minutes
        )

    log.info("All new PVCs are bound")

    # Check pods status
    for pod_obj in new_pods:
        helpers.wait_for_resource_state(
            resource=pod_obj, state=constants.STATUS_RUNNING, timeout=300  # Timeout given 5 minutes
        )
    log.info("All new pods are running")

    # Check pods are deleted
    for pod_obj in pods_to_delete:
        pod_obj.ocp.wait_for_delete(resource_name=pod_obj.name)

    log.info("All pods are deleted as expected.")

    # Check PVCs are deleted
    for pvc_obj in all_pvc_to_delete:
        pvc_obj.ocp.wait_for_delete(resource_name=pvc_obj.name)

    log.info("All PVCs are deleted as expected")
    return True
