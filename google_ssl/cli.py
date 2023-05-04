import click
from google_ssl.rotator import Rotator
from google_ssl.deployer import Deployer

bucket_option = click.option('--bucket', '-b', required=True, help='GCS bucket name')
yes_option = click.option('--yes', '-y', is_flag=True, help='Skip confirmation')

@click.group()
def cli():
    pass

@cli.command()
@bucket_option
@yes_option
def deploy(**kwargs):
    Deployer(**kwargs).run()

@cli.command()
@bucket_option
@yes_option
@click.option('--name', '-n', required=True, help="GCS key name, IE: path/to/file.crt")
@click.option('--proxies', '-p', default=None, help="Comma separated list of proxies to update")
def rotate(**kwargs):
    Rotator(**kwargs).run()

if __name__ == '__main__':
    cli()
