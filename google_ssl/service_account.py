import googleapiclient.discovery
import os
import subprocess
from google.oauth2 import service_account

class ServiceAccount:
    def __init__(self, bucket):
        self.bucket = bucket
        self.function_name = os.getenv("GS_FUNCTION_NAME") or "google-ssl-rotator"
        self.project_id = os.getenv("GOOGLE_PROJECT")

        self.service_account_name = self.function_name
        self.service_account_email = f"{self.service_account_name}@{self.project_id}.iam.gserviceaccount.com"

        # Construct the name of the service account
        # form: projects/{self.project_id}/serviceAccounts/{service_account_email}
        self.resource_id = f"projects/{self.project_id}/serviceAccounts/{self.service_account_email}"

        # Thanks: https://cloud.google.com/iam/docs/service-accounts-create#iam-service-accounts-create-python
        credentials = service_account.Credentials.from_service_account_file(
            filename=os.environ['GOOGLE_APPLICATION_CREDENTIALS'],
            scopes=['https://www.googleapis.com/auth/cloud-platform'])

        self.iam_service = googleapiclient.discovery.build(
            'iam', 'v1', credentials=credentials)

    def create(self):
        self.create_service_account()
        self.add_permissions()
        return self.service_account_email

    # To check service account:
    #     gcloud iam service-accounts list | grep " google-ssl-rotator"
    #     gcloud iam service-accounts get-iam-policy google-ssl-rotator@$GOOGLE_PROJECT.iam.gserviceaccount.com --format json > /tmp/service-accounts-get-iam-policy.json
    def create_service_account(self):
        try:
            sa = self.iam_service.projects().serviceAccounts().get(name=self.resource_id).execute()
            print(f"Service account {sa['email']} already exists")
        except googleapiclient.errors.HttpError as e:
            if e.resp.status == 404:
                print(f"Creating service account {self.service_account_name}")
                sa = self.iam_service.projects().serviceAccounts().create(
                    name='projects/' + self.project_id,
                    body={
                        'accountId': self.service_account_name,
                        'serviceAccount': {
                            'displayName': self.service_account_name
                        }
                    }).execute()
            else:
                raise e

        return sa

    # To check permission bindings
    #    gcloud projects get-iam-policy $GOOGLE_PROJECT --format json > /tmp/projects-get-iam-policy.json
    # Note: Tried to implement this with the Python API, but it was too complicated
    def add_permissions(self):
        member = f"serviceAccount:{self.service_account_email}"
        # https://cloud.google.com/run/docs/troubleshooting#unauthorized-client
        roles = [
            "roles/compute.loadBalancerAdmin",
            "roles/eventarc.eventReceiver",
            "roles/storage.objectViewer",
            "roles/run.invoker",
        ]

        current_policy = self.get_policy()

        for role in roles:
            if self.check_member_in_bindings(current_policy['bindings'], role, member):
                print(f"{member} already has permission {role}")
            else:
                self.add_permission(member, role)

    def add_permission(self, member, role):
        # Call the gcloud command to add the new binding to the IAM policy
        print(f"Adding permission binding: {member} {role}")
        cmd = f"gcloud projects add-iam-policy-binding {self.project_id} --member={member} --role='{role}' > /dev/null 2>&1"
        subprocess.run(cmd, shell=True, check=True)

    def get_policy(self):
        """Gets IAM policy for a project."""

        service = googleapiclient.discovery.build(
            "cloudresourcemanager", "v1"
        )
        policy = (
            service.projects()
            .getIamPolicy(
                resource=self.project_id,
                body={"options": {"requestedPolicyVersion": 1}},
            )
            .execute()
        )
        return policy

    # Example of bindings:
    # [{
    #   'role': 'projects/GOOGLE_PROJECT/roles/viewer',
    #   'members': ['serviceAccount:SERVICE_ACCOUNT_NAME@GOOGLE_PROJECT.iam.gserviceaccount.com']
    # },{
    #   'role': 'projects/GOOGLE_PROJECT/roles/editor',
    #   'members': ['serviceAccount:SERVICE_ACCOUNT_NAME@GOOGLE_PROJECT.iam.gserviceaccount.com']
    # }]
    def check_member_in_bindings(self, bindings, role, member):
        for binding in bindings:
            if binding['role'] == role and member in binding['members']:
                return True
        return False
