import logging

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import DiskCreateOption

logger = logging.getLogger(name=__file__)


class AZURE:
    """
    wrapper for Azure
    """
    _compute_client = None
    _credentials = None

    def __init__(self, subscription_id, client_id, secret, tenant):
        """
        Constructor for Azure class

        Args:
            subscription_id (str): Subscription ID
            client_id (str): Application (client) ID
            secret (): Client Secret
            tenant (str): Tenant ID
        """
        self._subscription_id = subscription_id
        self._client_id = client_id
        self._secret = secret
        self._tenant = tenant

    @property
    def get_credentials(self):
        """ Property for azure service principle credentials used to authenticate the client

        Returns:
            credentials: service principle credentials
            subscription_id: Subscription ID
        """
        self._credentials = ServicePrincipalCredentials(
            client_id=self._client_id,
            secret=self._secret,
            tenant=self._tenant
        )
        return self._credentials, self._subscription_id

    @property
    def compute_client(self):
        """ Property for Azure vm resource

        Returns:
            ComputeManagementClient instance for managing Azure vm resource
        """
        if not self._compute_client:
            self._compute_client = ComputeManagementClient(*self.get_credentials)
        return self._compute_client

    def get_node_by_attached_volume(self, volume):
        """
        Get the Azure Vm instance that has the volume attached to

        Args:
            volume (str): The volume name to get the Azure Vm according to

        Returns:
            vm: An Azure Vm instance

        """
        vm_list = self.compute_client.virtual_machines.list_all()

        for vm in vm_list:
            for disk in vm.storage_profile.data_disks:
                if disk.name == volume:
                    # node = vm.id.split("/")[-1]
                    # return node
                    return vm

    def detach_volume(self, volume, timeout=120):
        pass

def get_data_volumes(deviceset_pvs):
    """
    Get the instance data volume names

    Args:
        deviceset_pvs (list): PVC objects of the deviceset PVs

    Returns:
        list: Azure Vm Volume names

    """
    volume_name = [pv.get().get('spec').get('azureDisk').get('diskName') for pv in deviceset_pvs]
    return volume_name
