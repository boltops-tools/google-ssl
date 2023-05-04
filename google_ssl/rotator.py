from .common import *
from .base import Base
from google.cloud import compute_v1
from google.cloud import storage
import google # for google.api_core.exceptions.NotFound

class Rotator(Base):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.name = kwargs.get('name')
        self.proxies = kwargs.get('proxies')

        name_without_ext = ".".join(self.name.split(".")[:-1])
        self.key_path = name_without_ext + ".key"
        self.crt_path = name_without_ext + ".crt"
        self.download_key_path = "/tmp/" + self.key_path
        self.download_crt_path = "/tmp/" + self.crt_path
        self.cert_name = os.path.basename(name_without_ext)

        dirname = os.path.dirname(self.name)
        self.list_file_path = f"{dirname}/proxies.txt"

        self.storage_client = storage.Client()
        self.bucket_client = self.storage_client.bucket(self.bucket)

    def run(self):
        self.preview_confirmation()
        if "proxies.txt" in self.name:
            print("Uploaded target https proxy file: proxies.txt. Exiting from script")
            return

        both_exist = self.check_both_cert_files_exist()
        if not both_exist:
            print(f"Both cert files do not exist: {both_exist}")
            print(f"Both files {self.key_path} and {self.crt_path} need to exist to create the SSL certificate.")
            print("Exiting from script")
            return

        print(f"Both cert files exist: {both_exist}")
        self.download_cert_files()
        self.create_self_managed_ssl_certificate()
        self.update_target_https_proxy_certs()

    def preview_confirmation(self):
        """
        Prints out the preview of the script.
        """

        if os.getenv("YES") == "1" or self.yes:
            return

        proxies = self.proxies if self.proxies else self.list_file_path
        message = textwrap.dedent(f"""\
        Will use the information from:

            bucket:  {self.bucket}
            name:    {self.name}
            proxies: {proxies}

        To create a self-managed Google SSL certificate and update the target https proxies certs.
        """)
        print(message)

        response = input("Are you sure? (y/N): ")
        if response.lower() != "y":
            print("Exiting from script")
            exit(0)

    def check_both_cert_files_exist(self):
        """
        Checks if both cert files exist on a GCS bucket within the same folder.
        """

        # Check if the file exists
        key = self.bucket_client.blob(self.key_path).exists()
        crt = self.bucket_client.blob(self.crt_path).exists()
        print(f"Checking {self.key_path} exists. Exist: {key}")
        print(f"Checking {self.crt_path} exists. Exist: {crt}")
        return key and crt

    def download_cert_files(self):
        """
        Downloads both cert files from a GCS bucket within the same folder.
        """

        # Check if the file exists
        key = self.bucket_client.blob(self.key_path)
        crt = self.bucket_client.blob(self.crt_path)
        os.makedirs(os.path.dirname(self.download_key_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.download_crt_path), exist_ok=True)
        key.download_to_filename(self.download_key_path)
        crt.download_to_filename(self.download_crt_path)
        print(f"Downloaded {self.key_path} to {self.download_key_path}")
        print(f"Downloaded {self.crt_path} to {self.download_crt_path}")

    def create_self_managed_ssl_certificate(self):
        """
        Creates a self managed SSL certificate on a GCP project.
        """

        # API client
        compute_client = compute_v1.RegionSslCertificatesClient()

        # Create the SSL certificate
        print(f"Creating self-managed Google SSL cert: {self.cert_name}")
        ssl_certificate = {
            "name": self.cert_name,
            "private_key": open(self.download_key_path, "rb").read(),
            "certificate": open(self.download_crt_path, "rb").read(),
            "region": self.region,
        }
        already_exists = False
        try:
            operation = compute_client.insert(
                project = self.project_id,
                ssl_certificate_resource = ssl_certificate,
                region = self.region,
            )
        except google.api_core.exceptions.Conflict as e:
            print(e)
            print("SSL certificate already exists")
            already_exists = True

        if not already_exists:
            print(f"Created SSL certificate: {self.cert_name}")
            operation.result() # wait for result https://googleapis.dev/python/google-api-core/latest/operation.html

    def update_target_https_proxy_certs(self):
        """
        Updates all target HTTPS proxy certs.
        """

        proxies = None
        list_file = self.bucket_client.blob(self.list_file_path)

        if self.proxies: # cli rotate testing
            proxies = self.proxies.split(",")
        elif list_file.exists(): # cloud function
            print(f"Found {self.list_file_path} file")
            # read list file
            list_file_content = list_file.download_as_string().decode("utf-8")
            # split by new line and remove empty lines
            proxies = list(filter(None, list_file_content.split("\n")))
        else:
            print(f"Did not find {self.list_file_path} file. Not updating any target HTTPS proxies.")

        if proxies:
            for proxy in proxies:
                self.update_target_https_proxy_cert(proxy)

            self.show_check_hint(proxies)

    def update_target_https_proxy_cert(self, proxy):
        """
        Update target HTTP proxy certs.
        """

        # API client
        target_https_proxies = compute_v1.RegionTargetHttpsProxiesClient()

        # Update the target HTTPS proxy
        # https://cloud.google.com/python/docs/reference/compute/latest/google.cloud.compute_v1.services.target_https_proxies.TargetHttpsProxiesClient#google_cloud_compute_v1_services_target_https_proxies_TargetHttpsProxiesClient_set_ssl_certificates
        try:
            operation = target_https_proxies.set_ssl_certificates(
                project=self.project_id,
                target_https_proxy=proxy,
                region=self.region,
                region_target_https_proxies_set_ssl_certificates_request_resource={
                    "ssl_certificates": [
                        f"projects/{self.project_id}/regions/{self.region}/sslCertificates/{self.cert_name}"
                    ]
                }
            )
        except google.api_core.exceptions.NotFound as e:
            if " was not found" in str(e):
                print(e)
                print("ERROR: Target https proxy not found. Not updating.")
                return

        message = textwrap.dedent(f"""\
        Updating target HTTPS proxy with ssl cert.

            target https proxy: {proxy}
            cert name: {self.cert_name}

        This operation takes a few seconds to complete...
        """)
        print(message)
        operation.result() # wait for the operation to complete

    def show_check_hint(self, proxies):
        region_option = f"--region={self.region}" if self.region else ""
        commands = [
            f"    gcloud compute target-https-proxies describe {proxy} {region_option} | yq '.sslCertificates'"
            for proxy in proxies
        ]
        proxies_describe_commands = "\n".join(commands)

        message = textwrap.dedent(f"""\
You can check with:

    gcloud compute ssl-certificates list --format json | jq '.[].selfLink'
    gcloud compute ssl-certificates describe {self.cert_name} --region {self.region}
{proxies_describe_commands}
""")
        print(message)
