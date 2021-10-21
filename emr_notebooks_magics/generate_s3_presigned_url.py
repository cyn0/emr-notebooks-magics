# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import boto3
import botocore
import os
from IPython.core import magic_arguments
from IPython.core.error import UsageError
from IPython.core.magic import (Magics, magics_class, line_magic)
from IPython.display import display, HTML
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from .utils.str_utils import remove_prefix


@magics_class
class S3DownloadMagics(Magics):
    """
    Magic class that generates presigned url of a S3 object
    """

    def __init__(self, shell):
        super(S3DownloadMagics, self).__init__(shell)
        self.s3_client = boto3.client('s3')
        self.s3_resource = boto3.resource('s3')

    @magic_arguments.magic_arguments()
    @magic_arguments.argument(
        'path',
        type=str,
        help="""Full S3 path or file path relative to EMR workspace root"""
    )
    @magic_arguments.argument(
        '--expires-in',
        default=3600,
        type=int,
        help="""Number of seconds until the download URL expires.(Default 3600 seconds)"""
    )
    @line_magic
    def generate_s3_download_url(self, line):
        """
        Generates an url to download a S3 object. Argument can be either full S3 path or path relative to EMR Workspace root.
        Usage:
            generate_s3_download_url s3://path/to/s3/object
            generate_s3_download_url mynotebook.ipynb --expires-in 120
        """
        args = magic_arguments.parse_argstring(self.generate_s3_download_url, line)

        if not args.path.startswith("s3:"):
            args.path = os.environ["KERNEL_WORKSPACE_DIR_S3_PREFIX"] + args.path

        parsed_url = urlparse(args.path, allow_fragments=False)
        key = remove_prefix(parsed_url.path, "/")

        if not self._is_valid_s3_object(parsed_url.netloc, key):
            raise UsageError("{} is not a valid S3 object.".format(args.path))

        signed_url = self.s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': parsed_url.netloc,
                    'Key': key},
            ExpiresIn=args.expires_in)

        expiry_time = datetime.now(timezone.utc) + timedelta(seconds=args.expires_in)
        html = HTML("""<a href="{}">Click here</a> to download the S3 object. The link will expire at {} UTC"""
                    .format(signed_url, expiry_time.strftime('%Y-%m-%d %H:%M:%S'))
                    )
        display(html)

    def _is_valid_s3_object(self, s3_bucket, s3_prefix):
        if s3_prefix.endswith('/'):
            return False

        try:
            self.s3_resource.Object(s3_bucket, s3_prefix).load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            else:
                # Something else has gone wrong.
                raise UsageError("Something went wrong while making S3 request. Err code {}, error message {}"
                                 .format(e.response['Error']['Code'], e.response['Error']['Message']))
        else:
            return True
