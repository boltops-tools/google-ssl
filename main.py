import functions_framework
from google_ssl.rotator import Rotator

# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def event_handler(cloud_event):
    bucket = cloud_event.data['bucket']
    name = cloud_event.data['name']
    Rotator(bucket=bucket, name=name, yes=True).run()
