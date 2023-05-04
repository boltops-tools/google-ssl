# Google Cloud Function SSL Rotator Tool

This tool allows you to use Google cloud function to rotate a regional SSL cert for a regional Google target https proxy.

Note: This tool only supports regional google ssl certs and regional google target https proxies.

## Overview

You'll upload cert files to the configured GCS bucket, and it'll use the cert files to create a google ssl create and update the target https proxy. For clarity, here are the steps:

1. Upload your SSL cert files to your GCS Bucket, IE: cert1.key and cert1.crt
2. The Cloud function listens to the upload event.
3. Function creates a self-managed Google SSL Certificate with the same name as the uploaded file. IE: cert1
4. Function updates the target https proxy with the new cert.

## Notes

* The `GOOGLE_PROJECT` env variable must be set for this script to work.
* The Google Cloud Function is written in Python and uses purely the Google Cloud SDK. It does not use `gcloud`. This allows it to run on a Google Cloud Function.
* The tool comes with the `google-ssl deploy` command to deploy the function to Google Cloud functions. It creates the necessary resources, like an IAM service account with required permissions. While the Google Cloud Function itself does not require gcloud, some parts of the deploy command do rely on the `gcloud` cli. Note: There was an attempt to use the pure Google Cloud SDK, but it proved unsatisfactory. The SDK does not document deployment well, and the interface was too complex at the time.
* The tool also provides the ability to test locally. This helps speed up debugging, development, and testing.
* The tool provides a message explaining what it will do with a "Are you sure?" prompt. To bypass the message and prompt, use the `-y' option.

## Structure

Here's a suggested GCS bucket structure.

    gcs://$BUCKET/certs/$DOMAIN/

Here's an example with files uploaded.

    gcs://my-bucket/certs/example.com/proxies.txt
    gcs://my-bucket/certs/example.com/cert-name-1.key
    gcs://my-bucket/certs/example.com/cert-name-1.crt

Considerations:

* The cert name will be the name of the google ssl certification record that shows up with `gcloud compute ssl-certificates list`. Google ssl certificates need to be unique per Google project.
* The `.key` and `.crt` files and `proxies.txt` must exist before the script will create the google ssl certificate and continue on. Otherwise the script exits early with a message in the logs.
* Only a `.key` and `.crt` files will trigger a target https proxy update.

## proxies.txt

There needs to be a `proxies.txt` file in the same GCS folder. The `proxies.txt` lists target https proxies to be updated. This is because the only useful information passed to the cloud function in the received `cloud_event` object is the bucket name and filename path. So a `proxies.txt` contains a list of target proxie. If the `proxies.txt` does not exist, the script logs a message.

This file should be a list of target https proxies separated by newlines. Here's a `gcloud` command to help you grab a list to work with. You should remove most entries and only keep the proxies you want to update.

    gcloud compute target-https-proxies list --format json | jq -r '.[].name'

## Development Setup

For development, it is recommended to use Python virtualenv to set up the requirements. Here's a cheatsheet.

    virtualenv -p python3 .venv
    source .venv/bin/activate

## Install

Install the google-ssl tool.

    pip install --editable .

This installs the `google-ssl` command.

Note: The `pip install --editable .` creates a shim that points to your local folder of the tool. This means any code edits you make are reflected without having to reinstall unless you move the folder. TLDR: You only have to install once.

Alternatively, if you have poetry installed. You can run

    poetry install

See poetry site for detailed install docs: https://python-poetry.org/docs/#installation

## CLI Help Intro

CLI help:

    google-ssl
    google-ssl --help
    google-ssl deploy --help
    google-ssl rotate --help

You can also call the tool directly with python without installing the shim.

    python google_ssl/cli.py
    python google_ssl/cli.py --help
    python google_ssl/cli.py deploy --help
    python google_ssl/cli.py rotate --help

The shim makes the interface more user friendly, though and can be run from any location, not just the google-ssl project folder.

## Deploy

Deploy the code to google cloud functions.

    google-ssl deploy --bucket my-bucket

This simply uses [gcloud functions deploy](https://cloud.google.com/sdk/gcloud/reference/functions/deploy) to package up the code and deploy it to Google Cloud functions. The google function name is called `google-ssl-rotator` by default. It can be set with the `GS_FUNCTION_NAME` env var.

## Local Testing

This can be useful before deploying code to Google Cloud Functions.

Copy a `proxies.txt` file with a list of target https proxies you want to be updated and the SSL cert files you want to be used to create the Self-managed Google SSL Cert. Replace `CERT_NAME` with your own value. The cert name needs to be unique across the entire Google project.

    CERT_NAME=cert-name-1
    gsutil cp proxies.txt gs://my-bucket/certs/example.com/proxies.txt
    gsutil cp $CERT_NAME.key gs://my-bucket/certs/example.com/$CERT_NAME.key
    gsutil cp $CERT_NAME.crt gs://my-bucket/certs/example.com/$CERT_NAME.crt

The files must exist on the GCS bucket before running the next command: `rotate`.

The `rotate` command "triggers" the ssl cert update logic and downloads the cert files from the GCS bucket. It performs the **same** logic that the google cloud function performs. You're just manually triggering it for rapid testing and development.

    google-ssl rotate --bucket my-bucket --name certs/example.com/name.key

The nice thing about local testing is that you see the logs immediately in the same terminal.

You can also provide a `--proxies` option to specify which target https proxies to update. In this case, the `proxies.txt` is not downloaded and used. Example:

    google-ssl rotate --bucket my-bucket --name certs/example.com/name.key --proxies demo-target-https-proxy-dev

## Remote Testing: Cloud Function

You can build a test payload using the Google Cloud Function console **Testing** tab. Replace the `name` and `bucket` with some test values that exist in the GCS bucket.

```json
{
  "name": "certs/dev.example.com/test1.key",
  "bucket": "certs-bucket-dev",
  "contentType": "application/json",
  "metageneration": "1",
  "timeCreated": "2020-04-23T07:38:57.230Z",
  "updated": "2020-04-23T07:38:57.230Z"
}
```

It will display a `curl` command you can use in the Cloud Shell to test. It will return an "OK" http body response. Check the **Logs** tab to verify that it worked.

Last but not least, use gcloud to check that the google ssl cert was created and target https proxy was updated. Here's a cheatsheet with useful example commands:

    gcloud compute ssl-certificates list
    # useful to confirm certs are regional
    gcloud compute ssl-certificates list --format json | jq '.[].selfLink'
    gcloud compute ssl-certificates describe test1 --region us-central1
    gcloud compute target-https-proxies describe demo-target-https-proxy-dev --region us-central1 | yq '.sslCertificates'

The tool also shows a hint/tip with similar check commands upon completion.
