import logging
from ocs_ci.ocs import constants
from ocs_ci.ocs.resources.backingstore import BackingStore
from ocs_ci.ocs.exceptions import CommandFailed

from ocs_ci.framework import config
from ocs_ci.ocs.ocp import OCP
from ocs_ci.helpers.helpers import create_unique_resource_name

log = logging.getLogger(__name__)


class BucketClass:
    """
    A class that represents BucketClass objects

    """

    def __init__(
        self, name, backingstores, namespacestores, placement_policy, namespace_policy
    ):
        self.name = name
        self.backingstores = backingstores
        self.namespacestores = namespacestores
        self.placement_policy = placement_policy
        self.namespace_policy = namespace_policy

    # TODO: verify health of bucketclass

    def delete(self):
        log.info(f"Cleaning up bucket class {self.name}")

        OCP(namespace=config.ENV_DATA["cluster_namespace"]).exec_oc_cmd(
            command=f"delete bucketclass {self.name}", out_yaml_format=False
        )

        log.info(f"Verifying whether bucket class {self.name} exists after deletion")
        # Todo: implement deletion assertion


def bucket_class_factory(
    request, mcg_obj, backingstore_factory, namespace_store_factory
):
    """
    Create a bucket class factory. Calling this fixture creates a new custom bucket class.
    For a custom backingstore(s), provide the 'backingstore_dict' parameter.

    Args:
        request (object): Pytest built-in fixture
        mcg_obj (MCG): An MCG object containing the MCG S3 connection credentials
        backingstore_factory: Factory for backing store creation

    """
    interfaces = {
        "oc": mcg_obj.oc_create_bucketclass,
        "cli": mcg_obj.cli_create_bucketclass,
    }
    created_bucket_classes = []

    def _create_bucket_class(bucket_class_dict):
        """
        Creates and deletes all bucket classes that were created as part of the test

        Args:
            bucket_class_dict (dict): Dictionary containing the description of the bucket class.
                Possible keys and values are:
                - interface (str): The interface to use for creation of buckets.
                    OC | CLI

                - placement_policy (str): The Placement policy for this bucket class.
                    Spread | Mirror

                - backingstore_dict (dict): A dictionary compatible with the backing store factory
                  requirements. (Described in backingstore.py, under _create_backingstore)

                - namespace_policy_dict (dict):  A dictionary compatible with the namespace store factory.
                Needs to contain the following keys and values:
                    - type (str): Single | Multi | Cache
                    - namespacestore_dict (dict): Identical format to backingstore_dict, contains
                      data that's forwarded to cloud_uls_factory.

        Returns:
            BucketClass: A Bucket Class object.

        """
        if "interface" in bucket_class_dict:
            interface = bucket_class_dict["interface"]
            if interface.lower() not in interfaces.keys():
                raise RuntimeError(
                    f"Invalid interface type received: {interface}. "
                    f'available types: {", ".join(interfaces)}'
                )
        else:
            interface = "OC"

        namespace_policy = {}
        backingstores = None
        namespacestores = None
        placement_policy = None

        if "namespace_policy_dict" in bucket_class_dict:
            if "namespacestore_dict" in bucket_class_dict["namespace_policy_dict"]:
                nss_dict = bucket_class_dict["namespace_policy_dict"][
                    "namespacestore_dict"
                ]
                namespacestores = namespace_store_factory(interface, nss_dict)
                namespace_policy["type"] = bucket_class_dict["namespace_policy_dict"][
                    "type"
                ]
                namespace_policy["read_resources"] = [
                    nss.name for nss in namespacestores
                ]
                namespace_policy["write_resource"] = namespacestores[0].name

        elif "backingstore_dict" in bucket_class_dict:
            backingstores = [
                backingstore
                for backingstore in backingstore_factory(
                    interface, bucket_class_dict["backingstore_dict"]
                )
            ]
        else:
            backingstores = [
                BackingStore(constants.DEFAULT_NOOBAA_BACKINGSTORE, method="oc")
            ]

        if "placement_policy" in bucket_class_dict:
            placement_policy = bucket_class_dict["placement_policy"]
        else:
            placement_policy = "Spread"

        bucket_class_name = create_unique_resource_name(
            resource_description="bucketclass", resource_type=interface.lower()
        )
        interfaces[interface.lower()](
            name=bucket_class_name,
            backingstores=backingstores,
            placement=placement_policy,
            namespace_policy=namespace_policy,
        )
        bucket_class_object = BucketClass(
            bucket_class_name,
            backingstores,
            namespacestores,
            placement_policy,
            namespace_policy,
        )
        created_bucket_classes.append(bucket_class_object)
        return bucket_class_object

    def bucket_class_cleanup():
        for bucket_class in created_bucket_classes:
            try:
                bucket_class.delete()
            except CommandFailed as e:
                if "NotFound" in str(e):
                    log.warning(f"{bucket_class.name} could not be found in cleanup")
                else:
                    raise

    request.addfinalizer(bucket_class_cleanup)

    return _create_bucket_class
