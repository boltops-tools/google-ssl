import os

class Base:
    def __init__(self, **kwargs):
        self.bucket = kwargs.get('bucket')
        self.yes = kwargs.get('yes')
        self.project_id = os.getenv("GOOGLE_PROJECT")
        self.region = os.getenv("GOOGLE_REGION") or "us-central1"

    def print_env_vars(self):
        """
        Prints all environment variables. Useful for debugging.
        """

        print("Printing all environment variables in a pretty list sorted by key")
        for key, value in sorted(os.environ.items()):
            print(f"{key}={value}")
