from .common import *
from .base import Base
from google_ssl.service_account import ServiceAccount

class Deployer(Base):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.function_name = os.getenv("GS_FUNCTION_NAME") or "google-ssl-rotator"

    def run(self):
        self.preview_confirmation()
        print('Deploying google cloud function. May take a few minutes...')
        service_account_email = ServiceAccount(self.bucket).create()
        self.create_deploy_script(service_account_email)
        self.call_deploy_script()

    def preview_confirmation(self):
        """
        Prints out the preview of the script.
        """

        if os.getenv("YES") == "1" or self.yes:
            return

        message = textwrap.dedent(f"""\
        Will deploy resources:

        * Creates a Google Service Account named {self.function_name}
        * Creates a Google Cloud Function named {self.function_name}
        * With a bucket trigger on {self.bucket}
        """)
        print(message)

        response = input("Are you sure? (y/N): ")
        if response.lower() != "y":
            print("Exiting from script")
            exit(0)

    def call_deploy_script(self):
        # Call shell script and stream the output
        # This handles errors also
        parent_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        with subprocess.Popen(
            ["/tmp/deploy.sh"],
            stdout=subprocess.PIPE,
            universal_newlines=True,
            cwd=parent_directory # allows script to be called from any directory
        ) as proc:
            for line in proc.stdout:
                print(line, end='')
            # Wait for the process to finish and get the exit status
            exit_code = proc.wait()

        # Print the exit status
        if not exit_code == 0:
            print(f"Deploy failed. Exit status: {exit_code}")
            exit(exit_code)
        else:
            print("Deploy successful")

    def create_deploy_script(self, service_account_email):
        region = os.getenv("GOOGLE_REGION") or "us-central1"
        runtime = os.getenv("GS_RUNTIME") or "python311"
        trigger_location = os.getenv("GS_TRIGGER_LOCATION") or "us"

        bucket = self.bucket

        # Set command arguments
        gcloud = ["gcloud", "functions", "deploy", self.function_name]
        options = [
            f"--gen2",
            f"--entry-point", "event_handler",
            f"--region={region}",
            f"--runtime={runtime}",
            f"--service-account={service_account_email}",
            f"--update-env-vars=GOOGLE_PROJECT={self.project_id}",
            f"--trigger-location={trigger_location}",
            f"--trigger-event-filters='type=google.cloud.storage.object.v1.finalized'",
            f"--trigger-event-filters='bucket={bucket}'",
        ]
        args = gcloud + options

        # Execute command
        command = " ".join(args)
        print(f"=> {command}")

        # For some reason the command fails when executed directly
        # Write command to wrapper deploy.sh script and execute that instead
        with open("/tmp/deploy.sh", "w") as f:
            f.write("#!/bin/bash\n")
            f.write(command)
        # Make script executable
        os.chmod("/tmp/deploy.sh", 0o755)
